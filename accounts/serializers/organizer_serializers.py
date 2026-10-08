from rest_framework import serializers
from accounts.models import User, OrganizerProfile, SettlementAccount, StudioStaffMember
from events.models import Event, EventStaff
from events.utils.media_utils import upload_image_to_cloudinary


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
        return obj.paypal_email or ''

    def get_displayTitle(self, obj):
        return f"PayPal ({obj.paypal_email})"

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
            'isPrimary': 'is_primary',
        }
        for camel, snake in mapping.items():
            if camel in data:
                val = data.pop(camel)
                if isinstance(val, list) and len(val) == 1:
                    val = val[0]
                data[snake] = val

        data['method_type'] = 'paypal'
        return super().to_internal_value(data)

    def validate(self, attrs):
        attrs['method_type'] = 'paypal'
        email = (attrs.get('paypal_email') or '').strip()
        if not email:
            raise serializers.ValidationError({'paypalEmail': 'Valid PayPal email address is required.'})
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
                data['logo_url'] = upload_image_to_cloudinary(logo_val, folder='evento/organizers/logos')

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
        return EventStaff.objects.filter(event__organizer=obj.organizer, user=obj.user).count()

    def get_assignedEvents(self, obj):
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
