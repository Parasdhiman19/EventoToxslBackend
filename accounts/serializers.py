from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, OrganizerProfile, SettlementAccount, StudioStaffMember
from .constants import USER, MANAGER


class UserSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source='full_name', read_only=True)
    isOrganizer = serializers.SerializerMethodField()
    is_organizer = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'fullName', 'full_name', 'role', 'isOrganizer', 'is_organizer', 'created_at')

    def get_isOrganizer(self, obj):
        return getattr(obj, 'is_organizer', False)

    def get_is_organizer(self, obj):
        return getattr(obj, 'is_organizer', False)


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


import base64
import uuid
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def save_organizer_logo(data_uri, folder='organizers/logos'):
    """
    Decodes a base64 DataURL or file and saves it into Django's media storage.
    Returns relative media URL path (e.g. '/media/organizers/logos/abc.jpg').
    """
    if not data_uri or not isinstance(data_uri, str):
        return ''
    if data_uri.startswith('data:image/'):
        try:
            format_part, img_str = data_uri.split(';base64,')
            ext = format_part.split('/')[-1].lower()
            if ext == 'jpeg':
                ext = 'jpg'
            elif ext not in ['jpg', 'png', 'webp', 'gif', 'svg+xml']:
                ext = 'jpg'
            decoded_file = base64.b64decode(img_str)
            filename = f"{folder}/{uuid.uuid4().hex[:12]}.{ext}"
            saved_path = default_storage.save(filename, ContentFile(decoded_file))
            return f"/media/{saved_path}"
        except Exception:
            return data_uri
    return data_uri


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
    organizationName = serializers.CharField(source='organization_name', read_only=True)
    supportEmail = serializers.EmailField(source='support_email', read_only=True)
    supportPhone = serializers.CharField(source='support_phone', read_only=True)
    logoUrl = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    passPlatformFeeToBuyer = serializers.BooleanField(source='pass_platform_fee_to_buyer', read_only=True)
    allowTicketTransfers = serializers.BooleanField(source='allow_ticket_transfers', read_only=True)
    requireAttendeePhone = serializers.BooleanField(source='require_attendee_phone', read_only=True)
    autoRefundCancelledEvents = serializers.BooleanField(source='auto_refund_cancelled_events', read_only=True)
    instantSaleAlerts = serializers.BooleanField(source='instant_sale_alerts', read_only=True)
    dailySummaryDigest = serializers.BooleanField(source='daily_summary_digest', read_only=True)
    payoutDisbursementEmail = serializers.BooleanField(source='payout_disbursement_email', read_only=True)

    class Meta:
        model = OrganizerProfile
        fields = (
            'id', 'organization_name', 'organizationName', 'handle',
            'support_email', 'supportEmail', 'website', 'bio',
            'support_phone', 'supportPhone', 'instagram', 'logo_url', 'logoUrl',
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

    def get_logo_url(self, obj):
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
        if logo_val and isinstance(logo_val, str) and logo_val.startswith('data:image/'):
            data['logo_url'] = save_organizer_logo(logo_val)

        return super().to_internal_value(data)


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

