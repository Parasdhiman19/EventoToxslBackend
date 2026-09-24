import hashlib
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from .managers import UserManager
from .constants import *

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    full_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.CharField(max_length=500, blank=True, default='')
    bio = models.TextField(max_length=300, blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    email_notifications = models.BooleanField(default=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=CUSTOMER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        if not self.username and self.email:
            clean_name = self.email.split('@')[0].replace('.', '_').replace('-', '_').lower()
            clean_name = ''.join(c for c in clean_name if c.isalnum() or c == '_')[:30] or 'user'
            candidate = clean_name
            idx = 1
            while User.objects.filter(username__iexact=candidate).exclude(pk=self.pk).exists():
                candidate = f"{clean_name}_{idx}"
                idx += 1
            self.username = candidate
        super().save(*args, **kwargs)

    @property
    def is_organizer(self):
        try:
            if hasattr(self, 'organizer_profile') and self.organizer_profile is not None:
                return True
        except Exception:
            pass
        return self.role == 'manager'

    def __str__(self):
        return f"{self.email} ({'organizer' if self.is_organizer else 'customer'})"


class OrganizerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organizer_profile')
    organization_name = models.CharField(max_length=255, default='Nexus Productions Studio')
    handle = models.SlugField(max_length=100, unique=True, blank=True)
    support_email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    support_phone = models.CharField(max_length=50, blank=True)
    instagram = models.CharField(max_length=100, blank=True)
    logo_url = models.CharField(max_length=500, blank=True)

    # Ticketing Policies
    pass_platform_fee_to_buyer = models.BooleanField(default=True)
    allow_ticket_transfers = models.BooleanField(default=True)
    require_attendee_phone = models.BooleanField(default=True)
    auto_refund_cancelled_events = models.BooleanField(default=True)

    # Notification Preferences
    instant_sale_alerts = models.BooleanField(default=True)
    daily_summary_digest = models.BooleanField(default=True)
    payout_disbursement_email = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.handle:
            clean_email = self.user.email.split('@')[0].replace('.', '_')
            user_id_suffix = self.user.id or 'live'
            base_handle = f"{clean_email}_{user_id_suffix}"
            candidate = base_handle
            idx = 1
            while OrganizerProfile.objects.filter(handle=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_handle}_{idx}"
                idx += 1
            self.handle = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization_name} (@{self.handle})"


class SettlementAccount(models.Model):
    METHOD_CHOICES = (
        ('paypal', 'PayPal Account'),
        ('bank', 'Direct Bank Deposit'),
    )
    STATUS_CHOICES = (
        ('Primary', 'Primary'),
        ('Verified', 'Verified'),
    )

    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='settlement_accounts')
    method_type = models.CharField(max_length=20, choices=METHOD_CHOICES, default='bank')
    paypal_email = models.EmailField(blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    holder_name = models.CharField(max_length=255, blank=True)
    routing_number = models.CharField(max_length=100, blank=True)
    account_type = models.CharField(max_length=100, default='Direct Settlement')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Verified')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.status == 'Primary':
            self.is_primary = True
        elif self.is_primary:
            self.status = 'Primary'
        # If this is marked primary, unset other accounts for the same organizer
        if self.is_primary:
            SettlementAccount.objects.filter(organizer=self.organizer, is_primary=True).exclude(pk=self.pk).update(is_primary=False, status='Verified')
        super().save(*args, **kwargs)

    def __str__(self):
        if self.method_type == 'paypal':
            return f"PayPal ({self.paypal_email}) - {self.organizer.email}"
        return f"{self.bank_name} - {self.account_number} ({self.organizer.email})"


class StudioStaffMember(models.Model):
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='studio_staff_members'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='studio_staff_assignments'
    )
    role_title = models.CharField(
        max_length=100,
        default='Stage Coordinator',
        blank=True
    )
    default_can_view_attendees = models.BooleanField(
        default=True,
        help_text="Default permission: allows viewing guest list."
    )
    default_can_check_in = models.BooleanField(
        default=True,
        help_text="Default permission: allows scanning and checking in tickets at the gate."
    )
    default_can_edit_attendees = models.BooleanField(
        default=False,
        help_text="Default permission: allows modifying attendee notes/details."
    )
    phone = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organizer', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.role_title} ({self.organizer.email}'s Team)"


class EmailVerificationOTP(models.Model):
    PURPOSE_SIGNUP = 'signup'
    PURPOSE_RESET_PASSWORD = 'password_reset'
    PURPOSE_CHOICES = [
        (PURPOSE_SIGNUP, 'Signup Verification'),
        (PURPOSE_RESET_PASSWORD, 'Password Reset'),
    ]

    email = models.EmailField(db_index=True)
    otp_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default=PURPOSE_SIGNUP)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    expires_at = models.DateTimeField()
    resend_unlock_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'purpose', 'is_used']),
        ]

    def set_otp(self, raw_otp: str):
        self.otp_hash = hashlib.sha256(str(raw_otp).strip().encode('utf-8')).hexdigest()

    def check_otp(self, raw_otp: str) -> bool:
        candidate_hash = hashlib.sha256(str(raw_otp).strip().encode('utf-8')).hexdigest()
        return candidate_hash == self.otp_hash

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def can_resend(self) -> bool:
        return timezone.now() >= self.resend_unlock_at

    @property
    def remaining_attempts(self) -> int:
        return max(0, self.max_attempts - self.attempts)

    def __str__(self):
        return f"OTP for {self.email} ({self.purpose}) - Used: {self.is_used}"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    email = models.EmailField(db_index=True)
    token_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    resend_unlock_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'is_used']),
        ]

    def set_token(self, raw_token: str):
        self.token_hash = hashlib.sha256(str(raw_token).strip().encode('utf-8')).hexdigest()

    def check_token(self, raw_token: str) -> bool:
        candidate_hash = hashlib.sha256(str(raw_token).strip().encode('utf-8')).hexdigest()
        return candidate_hash == self.token_hash

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def can_resend(self) -> bool:
        return timezone.now() >= self.resend_unlock_at

    def __str__(self):
        return f"Reset Token for {self.email} - Used: {self.is_used}"




