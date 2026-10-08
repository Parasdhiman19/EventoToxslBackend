import os
import secrets
from datetime import timedelta
from django.utils import timezone
from rest_framework import status, views, permissions
from rest_framework.response import Response

from accounts.models import User, PasswordResetToken
from accounts.serializers import (
    RequestPasswordResetLinkSerializer,
    ValidateResetTokenSerializer,
    ConfirmPasswordResetSerializer,
)
from accounts.services.brevo_service import send_password_reset_link_email


class RequestPasswordResetLinkView(views.APIView):
    """
    Validates user email, generates a secure 32-byte token, and sends a password reset link email via Brevo.
    Enforces a 60s cooldown and hourly rate limit (max 5/hr).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RequestPasswordResetLinkSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        user = User.objects.filter(email__iexact=email).first()

        now = timezone.now()

        # Check resend cooldown on existing active reset token
        latest_token = PasswordResetToken.objects.filter(
            email=email,
            is_used=False
        ).first()

        if latest_token and not latest_token.can_resend:
            wait_seconds = int((latest_token.resend_unlock_at - now).total_seconds())
            wait_seconds = max(1, wait_seconds)
            return Response({
                'detail': f'Please wait {wait_seconds}s before requesting a new reset link.',
                'resend_after_seconds': wait_seconds
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Rate limiting: max 5 requests per hour
        one_hour_ago = now - timedelta(hours=1)
        hourly_count = PasswordResetToken.objects.filter(
            email=email,
            created_at__gte=one_hour_ago
        ).count()

        if hourly_count >= 5:
            return Response({
                'detail': 'Maximum password reset link requests exceeded for this hour. Please try again later.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Invalidate previous unused reset tokens for this email
        PasswordResetToken.objects.filter(
            email=email,
            is_used=False
        ).update(is_used=True)

        # Generate cryptographically secure token
        raw_token = secrets.token_urlsafe(32)

        # Create record
        token_record = PasswordResetToken(
            user=user,
            email=email,
            expires_at=now + timedelta(minutes=15),
            resend_unlock_at=now + timedelta(seconds=60),
            is_used=False
        )
        token_record.set_token(raw_token)
        token_record.save()

        # Build reset link URL
        frontend_base_url = os.getenv('FRONTEND_URL') or 'http://localhost:5173'
        frontend_base_url = frontend_base_url.rstrip('/')
        reset_url = f"{frontend_base_url}/account/reset-password?token={raw_token}&email={email}"

        # Send Email via Brevo
        sent_success, msg = send_password_reset_link_email(
            to_email=email,
            reset_url=reset_url,
            recipient_name=getattr(user, 'full_name', '')
        )

        if not sent_success:
            token_record.is_used = True
            token_record.save(update_fields=['is_used'])
            return Response({'detail': msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'message': f'A password reset link has been sent to {email}.',
            'email': email,
            'resend_after_seconds': 60,
            'expires_in_seconds': 900,
        }, status=status.HTTP_200_OK)


class ValidateResetTokenView(views.APIView):
    """
    Validates whether a reset token is still active and valid on page load.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ValidateResetTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        raw_token = serializer.validated_data['token']

        token_record = PasswordResetToken.objects.filter(
            email=email,
            is_used=False
        ).first()

        if not token_record or token_record.is_expired or not token_record.check_token(raw_token):
            return Response({
                'valid': False,
                'detail': 'This password reset link is invalid or has expired. Please request a new one.'
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'valid': True,
            'email': email,
            'message': 'Reset link is valid.'
        }, status=status.HTTP_200_OK)


class ConfirmPasswordResetView(views.APIView):
    """
    Verifies the reset token, updates the user's password, and invalidates the token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ConfirmPasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        raw_token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.is_active:
            return Response({
                'detail': 'Account not found or is currently disabled.'
            }, status=status.HTTP_400_BAD_REQUEST)

        token_record = PasswordResetToken.objects.filter(
            email=email,
            is_used=False
        ).first()

        if not token_record or token_record.is_expired or not token_record.check_token(raw_token):
            return Response({
                'detail': 'Invalid or expired password reset link. Please request a new one.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Mark token as used
        token_record.is_used = True
        token_record.save(update_fields=['is_used'])

        # Update password
        user.set_password(new_password)
        user.save(update_fields=['password'])

        # Notify user that password was reset
        try:
            from notifications.services import NotificationService
            NotificationService.send_password_changed(user)
        except Exception:
            pass

        return Response({
            'message': 'Your password has been reset successfully! You can now sign in with your new password.',
            'success': True
        }, status=status.HTTP_200_OK)
