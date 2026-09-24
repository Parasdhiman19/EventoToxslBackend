import secrets
from datetime import timedelta
from django.utils import timezone
from rest_framework import status, views, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

import os
from .models import User, OrganizerProfile, SettlementAccount, StudioStaffMember, EmailVerificationOTP, PasswordResetToken
from .constants import USER, MANAGER
from .permissions import IsManagerUser
from .services.brevo_service import send_otp_email, send_password_reset_otp_email, send_password_reset_link_email
from .serializers import (
    UserSerializer,
    UserProfileUpdateSerializer,
    ChangePasswordSerializer,
    SignupSerializer,
    LoginSerializer,
    RequestSignupOTPSerializer,
    VerifySignupOTPSerializer,
    RequestPasswordResetOTPSerializer,
    VerifyPasswordResetSerializer,
    RequestPasswordResetLinkSerializer,
    ValidateResetTokenSerializer,
    ConfirmPasswordResetSerializer,
    ResendOTPSerializer,
    OrganizerProfileSerializer,
    SettlementAccountSerializer,
    BecomeOrganizerSerializer,
    StudioStaffMemberSerializer,
    AddStudioStaffMemberSerializer,
)

COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    } 


def set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        samesite='Lax',
        secure=False,  # Set to True in HTTPS production
        max_age=COOKIE_MAX_AGE,
        path='/',
    )


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

        response = Response({
            'user': UserSerializer(user).data,
            'access': tokens['access'],
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
    Verifies the password reset OTP, updates the user's password, marks OTP as used,
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

        return Response({
            'message': 'Your password has been reset successfully! You can now sign in with your new password.',
            'success': True
        }, status=status.HTTP_200_OK)


class SignupView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            tokens = get_tokens_for_user(user)

            response = Response({
                'user': UserSerializer(user).data,
                'access': tokens['access'],
                'message': 'Account created successfully.'
            }, status=status.HTTP_201_CREATED)

            # Store refresh token exclusively in HttpOnly cookie
            set_refresh_cookie(response, tokens['refresh'])
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = get_tokens_for_user(user)

            response = Response({
                'user': UserSerializer(user).data,
                'access': tokens['access'],
                'message': 'Logged in successfully.'
            }, status=status.HTTP_200_OK)

            # Store refresh token exclusively in HttpOnly cookie
            set_refresh_cookie(response, tokens['refresh'])
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenRefreshView(views.APIView):
    """
    Reads the refresh token from HttpOnly cookie and returns a fresh access token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = (
            request.COOKIES.get('refresh_token') or 
            request.data.get('refresh') or 
            request.data.get('refreshToken') or
            request.data.get('refresh_token')
        )

        if not refresh_token:
            return Response(
                {'detail': 'Authentication refresh cookie not found.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)

            response = Response({
                'access': new_access_token,
            }, status=status.HTTP_200_OK)
            return response
        except (TokenError, InvalidToken):
            response = Response(
                {'detail': 'Refresh token is invalid or expired.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
            response.delete_cookie('refresh_token', path='/')
            return response


class LogoutView(views.APIView):
    """
    Clears the HttpOnly refresh token cookie on the backend.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        response = Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        response.delete_cookie('refresh_token', path='/')
        return response


class BecomeOrganizerView(views.APIView):
    """
    Attaches an OrganizerProfile to the currently authenticated user, activating organizer capability.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BecomeOrganizerSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            # Refetch/refresh user from db to ensure properties are fresh
            request.user.refresh_from_db()
            return Response({
                'user': UserSerializer(request.user).data,
                'message': 'Organizer capability activated successfully.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        request.user.refresh_from_db()
        return Response(UserSerializer(request.user, context={'request': request}).data)

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(
            instance=request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            user = serializer.save()
            user.refresh_from_db()
            return Response({
                'user': UserSerializer(user, context={'request': request}).data,
                'message': 'Profile updated successfully.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Password changed successfully.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OrganizerSettingsView(views.APIView):
    permission_classes = [IsManagerUser]

    def get_profile(self, user):
        profile, _ = OrganizerProfile.objects.get_or_create(
            user=user,
            defaults={
                'organization_name': f"{user.full_name}'s Studio" if user.full_name else 'Nexus Productions Studio',
            }
        )
        return profile

    def get(self, request):
        profile = self.get_profile(request.user)
        accounts = SettlementAccount.objects.filter(organizer=request.user)
        return Response({
            'profile': OrganizerProfileSerializer(profile, context={'request': request}).data,
            'settlementAccounts': SettlementAccountSerializer(accounts, many=True).data,
        })

    def patch(self, request):
        profile = self.get_profile(request.user)
        serializer = OrganizerProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                'profile': serializer.data,
                'message': 'Settings saved successfully.'
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SettlementAccountListView(views.APIView):
    permission_classes = [IsManagerUser]

    def get(self, request):
        accounts = SettlementAccount.objects.filter(organizer=request.user)
        return Response(SettlementAccountSerializer(accounts, many=True).data)

    def post(self, request):
        serializer = SettlementAccountSerializer(data=request.data)
        if serializer.is_valid():
            # If this is the first account, make it primary automatically
            existing_count = SettlementAccount.objects.filter(organizer=request.user).count()
            is_primary = serializer.validated_data.get('is_primary', False) or existing_count == 0
            serializer.save(organizer=request.user, is_primary=is_primary)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SettlementAccountDetailView(views.APIView):
    permission_classes = [IsManagerUser]

    def patch(self, request, pk):
        account = SettlementAccount.objects.filter(pk=pk, organizer=request.user).first()
        if not account:
            return Response({'detail': 'Settlement account not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SettlementAccountSerializer(account, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        account = SettlementAccount.objects.filter(pk=pk, organizer=request.user).first()
        if not account:
            return Response({'detail': 'Settlement account not found.'}, status=status.HTTP_404_NOT_FOUND)
        was_primary = account.is_primary
        account.delete()

        # If deleted account was primary, set another account as primary if available
        if was_primary:
            next_account = SettlementAccount.objects.filter(organizer=request.user).first()
            if next_account:
                next_account.is_primary = True
                next_account.save()

        return Response({'detail': 'Settlement account removed successfully.'})


class StudioStaffListView(views.APIView):
    permission_classes = [IsManagerUser]

    def get(self, request):
        staff_qs = StudioStaffMember.objects.filter(organizer=request.user).select_related('user')
        return Response(StudioStaffMemberSerializer(staff_qs, many=True, context={'request': request}).data)

    def post(self, request):
        serializer = AddStudioStaffMemberSerializer(
            data=request.data,
            context={'request': request, 'organizer': request.user}
        )
        if serializer.is_valid():
            record = serializer.save()
            return Response(StudioStaffMemberSerializer(record, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudioStaffDetailView(views.APIView):
    permission_classes = [IsManagerUser]

    def patch(self, request, pk):
        staff = StudioStaffMember.objects.filter(pk=pk, organizer=request.user).first()
        if not staff:
            return Response({'detail': 'Studio staff member not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        if 'roleTitle' in data or 'role_title' in data:
            staff.role_title = (data.get('roleTitle') or data.get('role_title') or '').strip() or staff.role_title
        if 'defaultCanViewAttendees' in data or 'default_can_view_attendees' in data:
            staff.default_can_view_attendees = bool(data.get('defaultCanViewAttendees', data.get('default_can_view_attendees')))
        if 'defaultCanCheckIn' in data or 'default_can_check_in' in data:
            staff.default_can_check_in = bool(data.get('defaultCanCheckIn', data.get('default_can_check_in')))
        if 'defaultCanEditAttendees' in data or 'default_can_edit_attendees' in data:
            staff.default_can_edit_attendees = bool(data.get('defaultCanEditAttendees', data.get('default_can_edit_attendees')))
        if 'phone' in data:
            staff.phone = (data.get('phone') or '').strip()
        if 'notes' in data:
            staff.notes = (data.get('notes') or '').strip()

        staff.save()
        return Response(StudioStaffMemberSerializer(staff, context={'request': request}).data)

    def delete(self, request, pk):
        staff = StudioStaffMember.objects.filter(pk=pk, organizer=request.user).first()
        if not staff:
            return Response({'detail': 'Studio staff member not found.'}, status=status.HTTP_404_NOT_FOUND)
        staff.delete()
        return Response({'detail': 'Staff member removed from studio directory successfully.'})

