import uuid
from django.db import models
from django.conf import settings
from accounts.models import SettlementAccount


class Payout(models.Model):
    STATUS_CHOICES = (
        ('Completed', 'Completed'),
        ('Processing', 'Processing'),
        ('Pending', 'Pending'),
        ('Failed', 'Failed'),
    )

    payout_number = models.CharField(max_length=50, unique=True, editable=False)
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payouts'
    )
    settlement_account = models.ForeignKey(
        SettlementAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payouts'
    )
    method_type = models.CharField(max_length=20, default='bank')
    destination_summary = models.CharField(max_length=255, blank=True)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee_deducted = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_disbursed = models.DecimalField(max_digits=12, decimal_places=2)
    paypal_batch_id = models.CharField(max_length=100, blank=True)
    paypal_payout_item_id = models.CharField(max_length=100, blank=True)
    utr_reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Completed')
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.payout_number:
            self.payout_number = f"PO-{uuid.uuid4().hex[:5].upper()}"
        if not self.utr_reference:
            self.utr_reference = f"UTR-{uuid.uuid4().hex[:10].upper()}"
        if not self.destination_summary and self.settlement_account:
            if self.settlement_account.method_type == 'paypal':
                self.destination_summary = f"PayPal ({self.settlement_account.paypal_email})"
            else:
                masked_acc = f"•••• {self.settlement_account.account_number[-4:]}" if len(self.settlement_account.account_number) >= 4 else self.settlement_account.account_number
                self.destination_summary = f"{self.settlement_account.bank_name} ({masked_acc})"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.payout_number} - ${self.net_disbursed} ({self.organizer.email})"

