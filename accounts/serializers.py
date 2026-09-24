from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, OrganizerProfile, SettlementAccount, StudioStaffMember, EmailVerificationOTP, PasswordResetToken
from .constants import USER, MANAGER


class UserSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source='full_name', read_only=True)
    avatarUrl = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    emailNotifications = serializers.BooleanField(source='email_notifications', read_only=True)
    isOrganizer = serializers.SerializerMethodField()
    is_organizer = serializers.SerializerMethodField()
    ticketsCount = serializers.SerializerMethodField()
    ordersCount = serializers.SerializerMethodField()
    savedCount = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'fullName', 'full_name',
            'avatar_url', 'avatarUrl', 'bio', 'phone', 'city',
            'email_notifications', 'emailNotifications',
            'role', 'isOrganizer', 'is_organizer',
            'ticketsCount', 'ordersCount', 'savedCount',
            'created_at'
        )

    def _resolve_avatar(self, obj):
        url = getattr(obj, 'avatar_url', '') or ''
        if not url:
            return ''
        if url.startswith(('http://', 'https://')):
            return url
        request = self.context.get('request')
        if url.startswith('/media/'):
            if request:
                return request.build_absolute_uri(url)
            return f"http://127.0.0.1:8000{url}"
        return url

    def get_avatarUrl(self, obj):
        return self._resolve_avatar(obj)

    def get_avatar_url(self, obj):
        return self._resolve_avatar(obj)

    def get_isOrganizer(self, obj):
        return getattr(obj, 'is_organizer', False)

    def get_is_organizer(self, obj):
        return getattr(obj, 'is_organizer', False)

    def get_ticketsCount(self, obj):
        try:
            from tickets.models import AttendeeTicket
            return AttendeeTicket.objects.filter(order__user=obj).count()
        except Exception:
            return 0

    def get_ordersCount(self, obj):
        try:
            from tickets.models import Order
            return Order.objects.filter(user=obj).count()
        except Exception:
            return 0

    def get_savedCount(self, obj):
        try:
            from events.models import SavedEvent
            return SavedEvent.objects.filter(user=obj).count()
        except Exception:
            return 0


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(max_length=50, required=False, allow_blank=True)
    fullName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    bio = serializers.CharField(max_length=300, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    avatar = serializers.CharField(required=False, allow_blank=True)
    avatarUrl = serializers.CharField(required=False, allow_blank=True)
    avatar_url = serializers.CharField(required=False, allow_blank=True)
    emailNotifications = serializers.BooleanField(required=False)
    email_notifications = serializers.BooleanField(required=False)

    class Meta:
        model = User
        fields = (
            'username', 'fullName', 'full_name', 'bio', 'phone', 'city',
            'avatar', 'avatarUrl', 'avatar_url',
            'emailNotifications', 'email_notifications'
        )

    def validate_username(self, value):
        if not value:
            return value
        cleaned = value.strip().lower()
        # Clean leading @ if user entered @username
        if cleaned.startswith('@'):
            cleaned = cleaned[1:]
        if len(cleaned) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters long.")
        if len(cleaned) > 30:
            raise serializers.ValidationError("Username cannot exceed 30 characters.")
        if not all(c.isalnum() or c == '_' for c in cleaned):
            raise serializers.ValidationError("Username can only contain alphanumeric characters and underscores.")
        
        user = self.instance
        if User.objects.filter(username__iexact=cleaned).exclude(pk=user.pk if user else None).exists():
            raise serializers.ValidationError("This username is already taken. Please choose another one.")
        return cleaned

    def validate_bio(self, value):
        if len(value) > 300:
            raise serializers.ValidationError("Bio cannot exceed 300 characters.")
        return value

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        mapping = {
            'fullName': 'full_name',
            'avatarUrl': 'avatar_url',
            'avatar': 'avatar_url',
            'emailNotifications': 'email_notifications',
        }
        for camel, snake in mapping.items():
            if camel in data:
                data[snake] = data.pop(camel)
        return super().to_internal_value(data)

    def update(self, instance, validated_data):
        if 'full_name' in validated_data:
            instance.full_name = validated_data['full_name'].strip()
        if 'username' in validated_data and validated_data['username']:
            instance.username = validated_data['username']
        if 'bio' in validated_data:
            instance.bio = validated_data['bio'].strip()
        if 'phone' in validated_data:
            instance.phone = validated_data['phone'].strip()
        if 'city' in validated_data:
            instance.city = validated_data['city'].strip()
        if 'email_notifications' in validated_data:
            instance.email_notifications = validated_data['email_notifications']

        avatar_val = validated_data.get('avatar_url')
        if avatar_val is not None:
            if avatar_val == '':
                instance.avatar_url = ''
            elif hasattr(avatar_val, 'read') or (isinstance(avatar_val, str) and (avatar_val.startswith('data:image/') or avatar_val.startswith(('http://', 'https://')))):
                from events.utils.media_utils import upload_image_to_cloudinary
                if hasattr(avatar_val, 'read') or avatar_val.startswith('data:image/'):
                    uploaded_url = upload_image_to_cloudinary(avatar_val, folder='evento/users/avatars')
                    instance.avatar_url = uploaded_url
                else:
                    instance.avatar_url = avatar_val

        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    oldPassword = serializers.CharField(write_only=True, required=False)
    old_password = serializers.CharField(write_only=True, required=False)
    newPassword = serializers.CharField(write_only=True, min_length=8, required=False)
    new_password = serializers.CharField(write_only=True, min_length=8, required=False)

    def validate(self, attrs):
        user = self.context['request'].user
        old_pw = attrs.get('old_password') or attrs.get('oldPassword')
        new_pw = attrs.get('new_password') or attrs.get('newPassword')

        if not old_pw:
            raise serializers.ValidationError({"oldPassword": "Current password is required."})
        if not new_pw:
            raise serializers.ValidationError({"newPassword": "New password is required."})
        if len(new_pw) < 8:
            raise serializers.ValidationError({"newPassword": "New password must be at least 8 characters long."})

        if not user.check_password(old_pw):
            raise serializers.ValidationError({"oldPassword": "The current password you entered is incorrect."})

        if old_pw == new_pw:
            raise serializers.ValidationError({"newPassword": "New password cannot be the same as your old password."})

        attrs['new_password'] = new_pw
        return attrs

    def save(self):
        user = self.context['request'].user
        new_password = self.validated_data['new_password']
        user.set_password(new_password)
        user.save(update_fields=['password'])
        return user


class BecomeOrganizerSerializer(serializers.Serializer):
    organizationName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    organization_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    supportEmail = serializers.EmailField(required=False, allow_blank=True)
    support_email = serializers.EmailField(required=False, allow_blank=True)
    supportPhone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    support_phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        user = self.context['request'].user
        org_name = (
            validated_data.get('organizationName') or
            validated_data.get('organization_name') or
            (f"{user.full_name}'s Studio" if user.full_name else "Nexus Productions Studio")
        )
        support_email = validated_data.get('supportEmail') or validated_data.get('support_email') or user.email
        support_phone = validated_data.get('supportPhone') or validated_data.get('support_phone') or ''

        profile, created = OrganizerProfile.objects.get_or_create(
            user=user,
            defaults={
                'organization_name': org_name,
                'support_email': support_email,
                'support_phone': support_phone,
                'website': validated_data.get('website') or '',
                'bio': validated_data.get('bio') or '',
            }
        )

        if not created:
            if org_name:
                profile.organization_name = org_name
            if support_email:
                profile.support_email = support_email
            if support_phone:
                profile.support_phone = support_phone
            if 'website' in validated_data:
                profile.website = validated_data['website']
            if 'bio' in validated_data:
                profile.bio = validated_data['bio']
            profile.save()

        # Update role on User model for manager sync
        if user.role != MANAGER:
            user.role = MANAGER
            user.save(update_fields=['role'])

        return profile


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


class SignupSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.CharField(default=USER, required=False)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower().strip()

    def create(self, validated_data):
        name = validated_data.get('fullName') or validated_data.get('full_name') or ''
        req_role = str(validated_data.get('role', USER)).lower()
        role_val = MANAGER if req_role in ['manager', 'organizer', '2'] else USER

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
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
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email', '').lower().strip()
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError("Both email and password are required.")

        request = self.context.get('request')
        user = authenticate(request=request, username=email, password=password)
        if not user:
            user = authenticate(request=request, email=email, password=password)

        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        attrs['user'] = user
        return attrs


from events.utils.media_utils import upload_image_to_cloudinary


def save_organizer_logo(data_uri_or_file, folder='evento/organizers/logos'):
    """
    Uploads organizer studio logo directly to Cloudinary and returns secure CDN URL.
    """
    if not data_uri_or_file:
        return ''
    return upload_image_to_cloudinary(data_uri_or_file, folder=folder)



class SettlementAccountSerializer(serializers.ModelSerializer):
    methodType = serializers.CharField(source='method_type', read_only=True)
    paypalEmail = serializers.EmailField(source='paypal_email', read_only=True)
    bankName = serializers.CharField(source='bank_name', read_only=True)
    accountNumber = serializers.CharField(source='account_number', read_only=True)
    holderName = serializers.CharField(source='holder_name', read_only=True)
    isPrimary = serializers.BooleanField(source='is_primary', read_only=True)
    maskedAccount = serializers.SerializerMethodField()
    displayTitle = serializers.SerializerMethodField()

    class Meta:
        model = SettlementAccount
        fields = (
            'id', 'method_type', 'methodType',
            'paypal_email', 'paypalEmail',
            'bank_name', 'bankName',
            'account_number', 'accountNumber',
            'holder_name', 'holderName',
            'status', 'is_primary', 'isPrimary',
            'maskedAccount', 'displayTitle',
            'created_at'
        )
        extra_kwargs = {
            'method_type': {'required': False},
            'paypal_email': {'required': False, 'allow_blank': True},
            'bank_name': {'required': False, 'allow_blank': True},
            'account_number': {'required': False, 'allow_blank': True},
            'holder_name': {'required': False, 'allow_blank': True},
            'is_primary': {'required': False},
        }

    def get_maskedAccount(self, obj):
        if obj.method_type == 'paypal':
            return obj.paypal_email
        if obj.account_number:
            return f"•••• {obj.account_number[-4:]}"
        return ''

    def get_displayTitle(self, obj):
        if obj.method_type == 'paypal':
            return f"PayPal ({obj.paypal_email})"
        return f"{obj.bank_name or 'Bank'} ({self.get_maskedAccount(obj)})"

    def to_internal_value(self, data):
        if hasattr(data, 'dict'):
            data = data.dict()
        elif hasattr(data, 'copy'):
            data = data.copy()
        else:
            data = dict(data)

        mapping = {
            'methodType': 'method_type',
            'paypalEmail': 'paypal_email',
            'bankName': 'bank_name',
            'accountNumber': 'account_number',
            'holderName': 'holder_name',
            'isPrimary': 'is_primary',
        }
        for camel, snake in mapping.items():
            if camel in data:
                val = data.pop(camel)
                if isinstance(val, list) and len(val) == 1:
                    val = val[0]
                data[snake] = val

        if 'method_type' not in data:
            if 'paypal_email' in data and data['paypal_email']:
                data['method_type'] = 'paypal'
            elif 'bank_name' in data or 'account_number' in data:
                data['method_type'] = 'bank'

        return super().to_internal_value(data)

    def validate(self, attrs):
        method_type = attrs.get('method_type', 'paypal')
        if method_type == 'paypal':
            email = attrs.get('paypal_email', '').strip()
            if not email:
                raise serializers.ValidationError({'paypalEmail': 'Valid PayPal email address is required.'})
        elif method_type == 'bank':
            if not attrs.get('bank_name', '').strip():
                raise serializers.ValidationError({'bankName': 'Bank name is required.'})
            if not attrs.get('account_number', '').strip():
                raise serializers.ValidationError({'accountNumber': 'Account number is required.'})
        return attrs


class OrganizerProfileSerializer(serializers.ModelSerializer):
    organizationName = serializers.CharField(source='organization_name', required=False, allow_blank=True)
    supportEmail = serializers.EmailField(source='support_email', required=False, allow_blank=True)
    supportPhone = serializers.CharField(source='support_phone', required=False, allow_blank=True)
    logoUrl = serializers.SerializerMethodField()
    logo_url = serializers.CharField(required=False, allow_blank=True)
    logo = serializers.CharField(required=False, allow_blank=True, write_only=True)
    passPlatformFeeToBuyer = serializers.BooleanField(source='pass_platform_fee_to_buyer', required=False)
    allowTicketTransfers = serializers.BooleanField(source='allow_ticket_transfers', required=False)
    requireAttendeePhone = serializers.BooleanField(source='require_attendee_phone', required=False)
    autoRefundCancelledEvents = serializers.BooleanField(source='auto_refund_cancelled_events', required=False)
    instantSaleAlerts = serializers.BooleanField(source='instant_sale_alerts', required=False)
    dailySummaryDigest = serializers.BooleanField(source='daily_summary_digest', required=False)
    payoutDisbursementEmail = serializers.BooleanField(source='payout_disbursement_email', required=False)

    class Meta:
        model = OrganizerProfile
        fields = (
            'id', 'organization_name', 'organizationName', 'handle',
            'support_email', 'supportEmail', 'website', 'bio',
            'support_phone', 'supportPhone', 'instagram', 'logo', 'logo_url', 'logoUrl',
            'pass_platform_fee_to_buyer', 'passPlatformFeeToBuyer',
            'allow_ticket_transfers', 'allowTicketTransfers',
            'require_attendee_phone', 'requireAttendeePhone',
            'auto_refund_cancelled_events', 'autoRefundCancelledEvents',
            'instant_sale_alerts', 'instantSaleAlerts',
            'daily_summary_digest', 'dailySummaryDigest',
            'payout_disbursement_email', 'payoutDisbursementEmail'
        )

    def _resolve_logo(self, path):
        if not path:
            return ''
        if path.startswith(('http://', 'https://')):
            return path
        request = self.context.get('request')
        if path.startswith('/media/'):
            if request:
                return request.build_absolute_uri(path)
            return f"http://127.0.0.1:8000{path}"
        return path

    def get_logoUrl(self, obj):
        return self._resolve_logo(obj.logo_url)

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        mapping = {
            'organizationName': 'organization_name',
            'supportEmail': 'support_email',
            'supportPhone': 'support_phone',
            'logoUrl': 'logo_url',
            'logo': 'logo_url',
            'passPlatformFeeToBuyer': 'pass_platform_fee_to_buyer',
            'allowTicketTransfers': 'allow_ticket_transfers',
            'requireAttendeePhone': 'require_attendee_phone',
            'autoRefundCancelledEvents': 'auto_refund_cancelled_events',
            'instantSaleAlerts': 'instant_sale_alerts',
            'dailySummaryDigest': 'daily_summary_digest',
            'payoutDisbursementEmail': 'payout_disbursement_email',
        }
        for camel, snake in mapping.items():
            if camel in data:
                data[snake] = data.pop(camel)

        logo_val = data.get('logo_url')
        if logo_val is not None:
            if logo_val == '':
                data['logo_url'] = ''
            elif isinstance(logo_val, str) and logo_val.startswith(('http://', 'https://')):
                data['logo_url'] = logo_val
            elif hasattr(logo_val, 'read') or (isinstance(logo_val, str) and logo_val.startswith('data:image/')):
                data['logo_url'] = save_organizer_logo(logo_val)

        return super().to_internal_value(data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class StudioStaffMemberSerializer(serializers.ModelSerializer):
    userId = serializers.IntegerField(source='user.id', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user = serializers.IntegerField(source='user.id', read_only=True)
    name = serializers.SerializerMethodField()
    fullName = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    avatar = serializers.SerializerMethodField()
    roleTitle = serializers.CharField(source='role_title')
    role = serializers.CharField(source='role_title', read_only=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    defaultCanViewAttendees = serializers.BooleanField(source='default_can_view_attendees')
    defaultCanCheckIn = serializers.BooleanField(source='default_can_check_in')
    defaultCanEditAttendees = serializers.BooleanField(source='default_can_edit_attendees')
    assignedEventsCount = serializers.SerializerMethodField()
    assignedEvents = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = StudioStaffMember
        fields = (
            'id', 'userId', 'user_id', 'user', 'name', 'fullName', 'full_name', 'username', 'email', 'avatar',
            'role_title', 'roleTitle', 'role',
            'phone', 'notes',
            'default_can_view_attendees', 'defaultCanViewAttendees',
            'default_can_check_in', 'defaultCanCheckIn',
            'default_can_edit_attendees', 'defaultCanEditAttendees',
            'assignedEventsCount', 'assignedEvents',
            'createdAt', 'created_at'
        )

    def get_name(self, obj):
        if obj.user.full_name and obj.user.full_name.strip():
            return obj.user.full_name.strip()
        return obj.user.email.split('@')[0]

    def get_fullName(self, obj):
        return self.get_name(obj)

    def get_full_name(self, obj):
        return self.get_name(obj)

    def get_username(self, obj):
        return obj.user.email.split('@')[0]

    def get_avatar(self, obj):
        name = self.get_name(obj)
        initials = ''.join([part[0].upper() for part in name.split()[:2]])
        return initials or 'ST'

    def get_assignedEventsCount(self, obj):
        from events.models import EventStaff
        return EventStaff.objects.filter(event__organizer=obj.organizer, user=obj.user).count()

    def get_assignedEvents(self, obj):
        from events.models import EventStaff
        staff_records = EventStaff.objects.filter(
            event__organizer=obj.organizer,
            user=obj.user
        ).select_related('event')
        return [
            {
                'id': s.event.id,
                'title': s.event.title,
                'staffRecordId': s.id,
                'roleTitle': s.role_title or obj.role_title,
                'canCheckIn': s.can_check_in,
                'canViewAttendees': s.can_view_attendees,
                'canEditAttendees': s.can_edit_attendees,
            }
            for s in staff_records
        ]


class AddStudioStaffMemberSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    userId = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
    roleTitle = serializers.CharField(max_length=100, required=False, default='Stage Coordinator')
    role_title = serializers.CharField(max_length=100, required=False)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    defaultCanViewAttendees = serializers.BooleanField(default=True, required=False)
    default_can_view_attendees = serializers.BooleanField(default=True, required=False)
    defaultCanCheckIn = serializers.BooleanField(default=True, required=False)
    default_can_check_in = serializers.BooleanField(default=True, required=False)
    defaultCanEditAttendees = serializers.BooleanField(default=False, required=False)
    default_can_edit_attendees = serializers.BooleanField(default=False, required=False)
    assignToEventId = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        organizer = self.context.get('organizer') or self.context.get('request').user
        user_id = attrs.get('userId') or attrs.get('user_id')
        email = (attrs.get('email') or '').lower().strip()

        target_user = None
        if user_id:
            target_user = User.objects.filter(pk=user_id, is_active=True).first()
        elif email:
            target_user = User.objects.filter(email__iexact=email, is_active=True).first()

        if not target_user:
            raise serializers.ValidationError({'detail': 'No registered active user found with the provided email or ID.'})

        if target_user == organizer:
            raise serializers.ValidationError({'detail': 'You cannot add yourself as a studio staff member.'})

        attrs['target_user'] = target_user
        attrs['organizer'] = organizer
        return attrs

    def create(self, validated_data):
        organizer = validated_data['organizer']
        target_user = validated_data['target_user']

        role_title = (
            validated_data.get('role_title')
            if 'role_title' in validated_data
            else validated_data.get('roleTitle', 'Stage Coordinator')
        )
        can_view = (
            validated_data.get('default_can_view_attendees')
            if 'default_can_view_attendees' in validated_data
            else validated_data.get('defaultCanViewAttendees', True)
        )
        can_check = (
            validated_data.get('default_can_check_in')
            if 'default_can_check_in' in validated_data
            else validated_data.get('defaultCanCheckIn', True)
        )
        can_edit = (
            validated_data.get('default_can_edit_attendees')
            if 'default_can_edit_attendees' in validated_data
            else validated_data.get('defaultCanEditAttendees', False)
        )
        phone = validated_data.get('phone', '').strip()
        notes = validated_data.get('notes', '').strip()

        staff_member, _ = StudioStaffMember.objects.update_or_create(
            organizer=organizer,
            user=target_user,
            defaults={
                'role_title': role_title,
                'default_can_view_attendees': can_view,
                'default_can_check_in': can_check,
                'default_can_edit_attendees': can_edit,
                'phone': phone,
                'notes': notes,
            }
        )

        assign_event_id = validated_data.get('assignToEventId')
        if assign_event_id:
            from events.models import Event, EventStaff
            event = Event.objects.filter(pk=assign_event_id, organizer=organizer).first()
            if event:
                EventStaff.objects.update_or_create(
                    event=event,
                    user=target_user,
                    defaults={
                        'role_title': role_title,
                        'can_view_attendees': can_view,
                        'can_check_in': can_check,
                        'can_edit_attendees': can_edit,
                    }
                )

        return staff_member

