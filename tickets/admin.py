from django.contrib import admin
from .models import Order, AttendeeTicket


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'event', 'tier', 'quantity', 'total_amount', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('order_number', 'user__email', 'event__title')


@admin.register(AttendeeTicket)
class AttendeeTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_code', 'attendee_name', 'event', 'tier', 'seat_or_gate', 'is_checked_in', 'checked_in_at')
    list_filter = ('is_checked_in',)
    search_fields = ('ticket_code', 'attendee_name', 'attendee_email')
