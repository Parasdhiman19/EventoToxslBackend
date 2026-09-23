from django.contrib import admin
from .models import Payout


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('payout_number', 'organizer', 'gross_amount', 'net_disbursed', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('payout_number', 'organizer__email', 'utr_reference')
