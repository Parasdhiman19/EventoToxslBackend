from rest_framework import serializers
from accounts.models import User, OrganizerProfile
from accounts.constants import MANAGER
from events.utils.media_utils import upload_image_to_cloudinary


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
