from django.db import models
from django.conf import settings
from django.utils import timezone


class HomepageBanner(models.Model):
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, default='')
    image_url = models.CharField(max_length=500)
    event = models.ForeignKey(
        'events.Event',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='banners'
    )
    cta_text = models.CharField(max_length=100, default='Get Tickets')
    custom_url = models.CharField(max_length=500, blank=True, default='')
    display_order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    active_from = models.DateTimeField(null=True, blank=True)
    active_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = 'Homepage Banner'
        verbose_name_plural = 'Homepage Banners'

    @property
    def is_currently_active(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.active_from and self.active_from > now:
            return False
        if self.active_until and self.active_until < now:
            return False
        return True

    def __str__(self):
        return f"Banner #{self.id}: {self.title} (Order: {self.display_order})"


class RecommendedEvent(models.Model):
    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='recommended_entries'
    )
    priority_rank = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority_rank', '-created_at']
        verbose_name = 'Recommended Event'
        verbose_name_plural = 'Recommended Events'

    @property
    def is_currently_active(self):
        if not self.is_active:
            return False
        if self.event.status != 'published' or self.event.is_ended:
            return False
        now = timezone.now()
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True

    def __str__(self):
        return f"#{self.priority_rank} Recommended: {self.event.title}"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='admin_audit_logs'
    )
    action_type = models.CharField(max_length=100, db_index=True)
    target_model = models.CharField(max_length=100, blank=True, default='')
    target_id = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField()
    changes_payload = models.JSONField(default=dict, blank=True)
    ip_address = models.CharField(max_length=45, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        actor_email = self.actor.email if self.actor else 'System'
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {actor_email} -> {self.action_type}: {self.description[:50]}"


class PlatformReport(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Investigating', 'Investigating'),
        ('Resolved', 'Resolved'),
        ('Dismissed', 'Dismissed'),
    )

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='filed_reports'
    )
    report_type = models.CharField(max_length=50, default='event')
    target_model = models.CharField(max_length=50, default='Event')
    target_id = models.CharField(max_length=100)
    reason = models.CharField(max_length=255)
    details = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='resolved_reports'
    )
    resolution_notes = models.TextField(blank=True, default='')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Platform Report'
        verbose_name_plural = 'Platform Reports'

    def __str__(self):
        return f"[{self.status}] Report on {self.target_model} #{self.target_id}: {self.reason}"


class PlatformSetting(models.Model):
    key = models.CharField(max_length=100, unique=True, primary_key=True)
    value = models.TextField(blank=True, default='')
    data_type = models.CharField(max_length=20, default='string')
    description = models.CharField(max_length=255, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Platform Setting'
        verbose_name_plural = 'Platform Settings'

    def __str__(self):
        return f"{self.key} = {self.value}"
