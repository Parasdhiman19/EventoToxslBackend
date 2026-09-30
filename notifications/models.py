from django.db import models
from django.conf import settings
from django.utils import timezone
from .constants import NOTIFICATION_TYPE_CHOICES


class Notification(models.Model):
    """
    Central notification record for the Evento platform.

    - recipient: the user this notification belongs to (always required)
    - actor: the user whose action triggered this (optional — None for system events)
    - notification_type: controlled vocabulary from constants.py
    - data: free-form JSON payload for frontend deep-link navigation
    - event / order / ticket: convenience FKs auto-cleared on related object deletion
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='triggered_notifications',
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPE_CHOICES,
        db_index=True,
    )

    title = models.CharField(max_length=255)
    message = models.TextField()

    # Structured payload for frontend navigation (e.g. {"event_id": 25, "order_id": 81})
    data = models.JSONField(default=dict, blank=True)

    # Optional FK shortcuts (auto-cleared if related object is deleted)
    event = models.ForeignKey(
        'events.Event',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='notifications',
    )
    order = models.ForeignKey(
        'tickets.Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='notifications',
    )
    ticket = models.ForeignKey(
        'tickets.AttendeeTicket',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='notifications',
    )

    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['recipient', 'is_read', '-created_at'],
                name='notif_recip_unread_idx'
            ),
            models.Index(
                fields=['recipient', '-created_at'],
                name='notif_recip_created_idx'
            ),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def mark_as_unread(self):
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=['is_read', 'read_at'])

    def __str__(self):
        status = '✓' if self.is_read else '●'
        return f"{status} [{self.notification_type}] → {self.recipient.email}: {self.title}"
