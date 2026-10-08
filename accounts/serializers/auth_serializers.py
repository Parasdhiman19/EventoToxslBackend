from rest_framework import serializers
from django.contrib.auth import authenticate
from accounts.models import User
from accounts.constants import USER, MANAGER
from events.models import SavedEvent
from tickets.models import AttendeeTicket, Order


class UserSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source='full_name', read_only=True)
    avatarUrl = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    organizationName = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    studioLogo = serializers.SerializerMethodField()
    logoUrl = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    organizerHandle = serializers.SerializerMethodField()
    organizer_handle = serializers.SerializerMethodField()
    emailNotifications = serializers.BooleanField(source='email_notifications', read_only=True)
    isOrganizer = serializers.SerializerMethodField()
    is_organizer = serializers.SerializerMethodField()
    isSuperAdmin = serializers.BooleanField(source='is_super_admin', read_only=True)
    is_super_admin = serializers.BooleanField(read_only=True)
    isStaff = serializers.BooleanField(source='is_staff', read_only=True)
    is_staff = serializers.BooleanField(read_only=True)
    isSuspended = serializers.BooleanField(source='is_suspended', read_only=True)
    is_suspended = serializers.BooleanField(read_only=True)
    ticketsCount = serializers.SerializerMethodField()
    ordersCount = serializers.SerializerMethodField()
    savedCount = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'fullName', 'full_name',
            'avatar_url', 'avatarUrl', 'bio', 'phone', 'city',
            'organizationName', 'organization_name', 'studioLogo', 'logoUrl', 'logo_url',
            'organizerHandle', 'organizer_handle',
            'email_notifications', 'emailNotifications',
            'role', 'isOrganizer', 'is_organizer',
            'isSuperAdmin', 'is_super_admin', 'isStaff', 'is_staff',
            'isSuspended', 'is_suspended',
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

    def _resolve_url(self, url):
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

    def get_organizationName(self, obj):
        try:
            if hasattr(obj, 'organizer_profile') and obj.organizer_profile:
                return obj.organizer_profile.organization_name
        except Exception:
            pass
        return ''

    def get_organization_name(self, obj):
        return self.get_organizationName(obj)

    def get_studioLogo(self, obj):
        try:
            if hasattr(obj, 'organizer_profile') and obj.organizer_profile:
                return self._resolve_url(obj.organizer_profile.logo_url)
        except Exception:
            pass
        return ''

    def get_logoUrl(self, obj):
        return self.get_studioLogo(obj)

    def get_logo_url(self, obj):
        return self.get_studioLogo(obj)

    def get_organizerHandle(self, obj):
        try:
            if hasattr(obj, 'organizer_profile') and obj.organizer_profile:
                return obj.organizer_profile.handle
        except Exception:
            pass
        return ''

    def get_organizer_handle(self, obj):
        return self.get_organizerHandle(obj)

    def get_isOrganizer(self, obj):
        return getattr(obj, 'is_organizer', False)

    def get_is_organizer(self, obj):
        return getattr(obj, 'is_organizer', False)

    def get_ticketsCount(self, obj):
        try:
            return AttendeeTicket.objects.filter(order__user=obj).count()
        except Exception:
            return 0

    def get_ordersCount(self, obj):
        try:
            return Order.objects.filter(user=obj).count()
        except Exception:
            return 0

    def get_savedCount(self, obj):
        try:
            return SavedEvent.objects.filter(user=obj).count()
        except Exception:
            return 0


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
        from accounts.models import OrganizerProfile
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


