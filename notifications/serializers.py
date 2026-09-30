from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Full notification serializer for API responses and WebSocket push payloads.
    Only exposes fields the frontend needs — no sensitive or internal fields.
    """
    id = serializers.IntegerField(read_only=True)
    notificationType = serializers.CharField(source='notification_type', read_only=True)
    isRead = serializers.BooleanField(source='is_read', read_only=True)
    readAt = serializers.DateTimeField(source='read_at', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    actorName = serializers.SerializerMethodField()
    actorAvatar = serializers.SerializerMethodField()
    timeAgo = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            'id',
            'notificationType',
            'title',
            'message',
            'data',
            'isRead',
            'readAt',
            'createdAt',
            'timeAgo',
            'actorName',
            'actorAvatar',
        )

    def get_actorName(self, obj):
        if obj.actor:
            return obj.actor.full_name or obj.actor.email.split('@')[0].title()
        return None

    def get_actorAvatar(self, obj):
        if obj.actor:
            return getattr(obj.actor, 'avatar_url', '') or ''
        return None

    def get_timeAgo(self, obj):
        """Return a human-readable relative time string."""
        from django.utils import timezone
        import math

        now = timezone.now()
        diff = now - obj.created_at
        seconds = int(diff.total_seconds())

        if seconds < 60:
            return 'just now'
        elif seconds < 3600:
            m = seconds // 60
            return f'{m} minute{"s" if m != 1 else ""} ago'
        elif seconds < 86400:
            h = seconds // 3600
            return f'{h} hour{"s" if h != 1 else ""} ago'
        elif seconds < 604800:
            d = seconds // 86400
            return f'{d} day{"s" if d != 1 else ""} ago'
        else:
            return obj.created_at.strftime('%b %d, %Y')
