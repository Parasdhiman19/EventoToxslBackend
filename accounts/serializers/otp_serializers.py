from rest_framework import serializers
from accounts.models import User, EmailVerificationOTP
from accounts.constants import USER


class RequestSignupOTPSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.CharField(default=USER, required=False)

    def validate_email(self, value):
        cleaned_email = value.lower().strip()
        if User.objects.filter(email__iexact=cleaned_email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return cleaned_email


class VerifySignupOTPSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.CharField(default=USER, required=False)
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        cleaned_otp = str(value).strip()
        if not cleaned_otp.isdigit() or len(cleaned_otp) != 6:
            raise serializers.ValidationError("OTP must be a 6-digit number.")
        return cleaned_otp


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.CharField(default=EmailVerificationOTP.PURPOSE_SIGNUP, required=False)

    def validate_email(self, value):
        return value.lower().strip()


class RequestPasswordResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        cleaned_email = value.lower().strip()
        user = User.objects.filter(email__iexact=cleaned_email).first()
        if not user:
            raise serializers.ValidationError("No account found registered with this email address.")
        if not user.is_active:
            raise serializers.ValidationError("This account is currently disabled. Please contact support.")
        return cleaned_email


class VerifyPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        cleaned_otp = str(value).strip()
        if not cleaned_otp.isdigit() or len(cleaned_otp) != 6:
            raise serializers.ValidationError("OTP must be a 6-digit number.")
        return cleaned_otp


class RequestPasswordResetLinkSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        cleaned_email = value.lower().strip()
        user = User.objects.filter(email__iexact=cleaned_email).first()
        if not user:
            raise serializers.ValidationError("No account found registered with this email address.")
        if not user.is_active:
            raise serializers.ValidationError("This account is currently disabled. Please contact support.")
        return cleaned_email


class ValidateResetTokenSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField(min_length=10)

    def validate_email(self, value):
        return value.lower().strip()


class ConfirmPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField(min_length=10)
    new_password = serializers.CharField(write_only=True, min_length=8, required=False)
    newPassword = serializers.CharField(write_only=True, min_length=8, required=False)

    def validate_email(self, value):
        return value.lower().strip()

    def validate(self, attrs):
        password = attrs.get('new_password') or attrs.get('newPassword')
        if not password:
            raise serializers.ValidationError({"new_password": "New password is required."})
        attrs['new_password'] = password
        return attrs
