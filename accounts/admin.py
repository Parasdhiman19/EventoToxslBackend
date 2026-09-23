from django.contrib import admin
from .models import User, OrganizerProfile, SettlementAccount


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'role', 'is_active', 'is_staff', 'created_at')
    search_fields = ('email', 'full_name')
    list_filter = ('role', 'is_staff', 'is_active')


@admin.register(OrganizerProfile)
class OrganizerProfileAdmin(admin.ModelAdmin):
    list_display = ('organization_name', 'handle', 'user', 'support_email')
    search_fields = ('organization_name', 'handle', 'user__email')


@admin.register(SettlementAccount)
class SettlementAccountAdmin(admin.ModelAdmin):
    list_display = ('bank_name', 'account_number', 'holder_name', 'organizer', 'status')
    list_filter = ('status',)
    search_fields = ('bank_name', 'account_number', 'holder_name', 'organizer__email')