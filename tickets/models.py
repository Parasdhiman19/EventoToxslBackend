import uuid
from django.db import models
from django.conf import settings
from events.models import Event, TicketTier


class Order(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Paid', 'Paid'),
        ('Failed', 'Failed'),
        ('Cancelled', 'Cancelled'),
        ('Refunded', 'Refunded'),
        ('Completed', 'Completed'),
    )

    order_number = models.CharField(max_length=50, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    tier = models.ForeignKey(
        TicketTier,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    fees = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=100, default='UPI • Axis Bank')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Confirmed')
    paypal_order_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    paypal_capture_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_number} - {self.user.email} (${self.total_amount})"


class AttendeeTicket(models.Model):
    ticket_code = models.CharField(max_length=50, unique=True, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='attendees'
    )
    tier = models.ForeignKey(
        TicketTier,
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    attendee_name = models.CharField(max_length=255)
    attendee_email = models.EmailField()
    seat_or_gate = models.CharField(max_length=100, default='Main Gate')
    is_checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.ticket_code:
            prefix = "EV-TCK"
            if "VIP" in self.tier.name.upper():
                prefix = "EV-VIP"
            elif "DEL" in self.tier.name.upper() or "DELEGATE" in self.tier.name.upper():
                prefix = "EV-DEL"
            self.ticket_code = f"{prefix}-{self.event.id}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_code} - {self.attendee_name} ({self.event.title})"
