import secrets
from datetime import timedelta
from django.utils import timezone
from rest_framework import status, views, permissions
from rest_framework.response import Response

from accounts.models import User, OrganizerProfile, EmailVerificationOTP
from accounts.constants import USER, MANAGER
from accounts.serializers import (
    UserSerializer,
    RequestSignupOTPSerializer,
    VerifySignupOTPSerializer,
    RequestPasswordResetOTPSerializer,
    VerifyPasswordResetSerializer,
)
from accounts.services.brevo_service import send_otp_email, send_password_reset_otp_email
from .cookie_utils import get_tokens_for_user, set_refresh_cookie


class RequestSignupOTPView(views.APIView):
    """
    Validates signup details and generates a 6-digit OTP sent via Brevo.
    Enforces a 60-second resend cooldown and hourly rate limit (max 5/hr).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RequestSignupOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        name = serializer.validated_data.get('fullName') or serializer.validated_data.get('full_name') or ''

        now = timezone.now()

        # Check resend cooldown on existing active OTP
        latest_active_otp = EmailVerificationOTP.objects.filter(
            email=email,
            purpose=EmailVerificationOTP.PURPOSE_SIGNUP,
            is_used=False
        ).first()

        if latest_active_otp and not latest_active_otp.can_resend:
            wait_seconds = int((latest_active_otp.resend_unlock_at - now).total_seconds())
            wait_seconds = max(1, wait_seconds)
            return Response({
                'detail': f'Please wait {wait_seconds}s before requesting a new code.',
                'resend_after_seconds': wait_seconds
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Rate limiting: max 5 OTP requests in the last hour for this email
        one_hour_ago = now - timedelta(hours=1)
        hourly_count = EmailVerificationOTP.objects.filter(
            email=email,
            purpose=EmailVerificationOTP.PURPOSE_SIGNUP,
            created_at__gte=one_hour_ago
        ).count()

        if hourly_count >= 5:
            return Response({
                'detail': 'Maximum verification requests exceeded for this hour. Please try again later.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Invalidate previous unused signup OTPs for this email
        EmailVerificationOTP.objects.filter(
            email=email,
            purpose=EmailVerificationOTP.PURPOSE_SIGNUP,
            is_used=False
        ).update(is_used=True)

        # Generate secure 6-digit code
        raw_otp = f"{secrets.randbelow(900000) + 100000}"

        # Create record
        otp_record = EmailVerificationOTP(
            email=email,
            purpose=EmailVerificationOTP.PURPOSE_SIGNUP,
            expires_at=now + timedelta(minutes=5),
            resend_unlock_at=now + timedelta(seconds=60),
            attempts=0,
            max_attempts=5,
            is_used=False
        )
        otp_record.set_otp(raw_otp)
        otp_record.save()

        # Send Email via Brevo
        sent_success, msg = send_otp_email(
            to_email=email,
            otp_code=raw_otp,
            recipient_name=name
        )

        if not sent_success:
            # If sending failed, invalidate record and return error
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            return Response({'detail': msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'message': f'A 6-digit verification code has been sent to {email}.',
            'email': email,
            'resend_after_seconds': 60,
            'expires_in_seconds': 300,
        }, status=status.HTTP_200_OK)


class VerifySignupOTPView(views.APIView):
    """
    Verifies the 6-digit OTP code, checks attempt limits & expiry,
    and upon success creates the User record and issues JWT tokens.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifySignupOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        input_otp = serializer.validated_data['otp']
        name = serializer.validated_data.get('fullName') or serializer.validated_data.get('full_name') or ''
        password = serializer.validated_data['password']
        req_role = str(serializer.validated_data.get('role', USER)).lower()
        role_val = MANAGER if req_role in ['manager', 'organizer', '2'] else USER

        now = timezone.now()

        # Fetch latest unused OTP record
        otp_record = EmailVerificationOTP.objects.filter(
            email=email,
            purpose=EmailVerificationOTP.PURPOSE_SIGNUP,
            is_used=False
        ).first()

        if not otp_record:
            return Response({
                'detail': 'No active verification code found for this email. Please request a new one.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check expiry
        if otp_record.is_expired:
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            return Response({
                'detail': 'Verification code has expired. Please request a new code.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check max attempts
        if otp_record.attempts >= otp_record.max_attempts:
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            return Response({
                'detail': 'Maximum verification attempts exceeded. Please request a new code.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Verify OTP code
        if not otp_record.check_otp(input_otp):
            otp_record.attempts += 1
            if otp_record.attempts >= otp_record.max_attempts:
                otp_record.is_used = True
                otp_record.save(update_fields=['attempts', 'is_used'])
                return Response({
                    'detail': 'Incorrect verification code. Maximum attempts reached. Please request a new code.'
                }, status=status.HTTP_400_BAD_REQUEST)

            otp_record.save(update_fields=['attempts'])
            remaining = otp_record.remaining_attempts
            return Response({
                'detail': f'Incorrect verification code. {remaining} {"attempt" if remaining == 1 else "attempts"} remaining.',
                'remaining_attempts': remaining
            }, status=status.HTTP_400_BAD_REQUEST)

        # Success - Mark OTP as used
        otp_record.is_used = True
        otp_record.save(update_fields=['is_used'])

        # Double check if user already exists
        if User.objects.filter(email__iexact=email).exists():
            return Response({
                'detail': 'An account with this email already exists.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create user account
        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=name,
            role=role_val
        )

        if user.role == MANAGER:
            OrganizerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'organization_name': f"{user.full_name}'s Studio" if user.full_name else "Nexus Productions Studio",
                }
            )

        tokens = get_tokens_for_user(user)

        # Welcome notification
        try:
            from notifications.services import NotificationService
            NotificationService.send_welcome(user)
            if user.role == MANAGER:
                NotificationService.send_organizer_profile_activated(user)
        except Exception:
            pass

        response = Response({
            'user': UserSerializer(user).data,
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'message': 'Account verified and created successfully.'
        }, status=status.HTTP_201_CREATED)

        set_refresh_cookie(response, tokens['refresh'])
        return response


class RequestPasswordResetOTPView(views.APIView):
    """
    Validates user email, generates a 6-digit password reset OTP, and dispatches it via Brevo.
    Enforces a 60s cooldown and hourly rate limit (max 5/hr).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RequestPasswordResetOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        user = User.objects.filter(email__iexact=email).first()

        now = timezone.now()

        # Check resend cooldown on existing active reset OTP
        latest_active_otp = EmailVerificationOTP.objects.filter(
            email=email,
            purpose=EmailVerificationOTP.PURPOSE_RESET_PASSWORD,
            is_used=False
        ).first()

        if latest_active_otp and not latest_active_otp.can_resend:
            wait_seconds = int((latest_active_otp.resend_unlock_at - now).total_seconds())
            wait_seconds = max(1, wait_seconds)
            return Response({
                'detail': f'Please wait {wait_seconds}s before requesting a new code.',
                'resend_after_seconds': wait_seconds
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Rate limiting: max 5 requests per hour
        one_hour_ago = now - timedelta(hours=1)
        hourly_count = EmailVerificationOTP.objects.filter(
            email=email,
            purpose=EmailVerificationOTP.PURPOSE_RESET_PASSWORD,
            created_at__gte=one_hour_ago
        ).count()

        if hourly_count >= 5:
            return Response({
                'detail': 'Maximum password reset requests exceeded for this hour. Please try again later.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Invalidate previous unused reset OTPs for this email
        EmailVerificationOTP.objects.filter(
            email=email,
            purpose=EmailVerificationOTP.PURPOSE_RESET_PASSWORD,
            is_used=False
        ).update(is_used=True)

        # Generate secure 6-digit code
        raw_otp = f"{secrets.randbelow(900000) + 100000}"

        # Create record
        otp_record = EmailVerificationOTP(
            email=email,
            purpose=EmailVerificationOTP.PURPOSE_RESET_PASSWORD,
            expires_at=now + timedelta(minutes=5),
            resend_unlock_at=now + timedelta(seconds=60),
            attempts=0,
            max_attempts=5,
            is_used=False
        )
        otp_record.set_otp(raw_otp)
        otp_record.save()

        # Send Email via Brevo
        sent_success, msg = send_password_reset_otp_email(
            to_email=email,
            otp_code=raw_otp,
            recipient_name=getattr(user, 'full_name', '')
        )

        if not sent_success:
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            return Response({'detail': msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'message': f'A 6-digit password reset code has been sent to {email}.',
            'email': email,
            'resend_after_seconds': 60,
            'expires_in_seconds': 300,
        }, status=status.HTTP_200_OK)


class VerifyPasswordResetView(views.APIView):
    """
    Verifies the password reset OTP, marks OTP as used,
    and returns JWT credentials for instant auto-login.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyPasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        input_otp = serializer.validated_data['otp']

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.is_active:
            return Response({
                'detail': 'Account not found or is currently disabled.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Fetch latest unused reset OTP record
        otp_record = EmailVerificationOTP.objects.filter(
            email=email,
            purpose=EmailVerificationOTP.PURPOSE_RESET_PASSWORD,
            is_used=False
        ).first()

        if not otp_record:
            return Response({
                'detail': 'No active verification request found for this email. Please request a new code.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check expiry
        if otp_record.is_expired:
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            return Response({
                'detail': 'Verification code has expired. Please request a new code.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check max attempts
        if otp_record.attempts >= otp_record.max_attempts:
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            return Response({
                'detail': 'Maximum verification attempts exceeded. Please request a new code.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Verify OTP code
        if not otp_record.check_otp(input_otp):
            otp_record.attempts += 1
            if otp_record.attempts >= otp_record.max_attempts:
                otp_record.is_used = True
                otp_record.save(update_fields=['attempts', 'is_used'])
                return Response({
                    'detail': 'Incorrect code. Maximum attempts reached. Please request a new code.'
                }, status=status.HTTP_400_BAD_REQUEST)

            otp_record.save(update_fields=['attempts'])
            remaining = otp_record.remaining_attempts
            return Response({
                'detail': f'Incorrect verification code. {remaining} {"attempt" if remaining == 1 else "attempts"} remaining.',
                'remaining_attempts': remaining
            }, status=status.HTTP_400_BAD_REQUEST)

        # Mark OTP as used
        otp_record.is_used = True
        otp_record.save(update_fields=['is_used'])

        # Issue JWT tokens for instant auto-login (Password is NOT changed)
        tokens = get_tokens_for_user(user)

        response = Response({
            'user': UserSerializer(user).data,
            'access': tokens['access'],
            'message': 'Account verified successfully! You are now logged in.'
        }, status=status.HTTP_200_OK)

        set_refresh_cookie(response, tokens['refresh'])
        return response
