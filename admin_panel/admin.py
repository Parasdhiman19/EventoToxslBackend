from django.contrib import admin
from .models import HomepageBanner, RecommendedEvent, AuditLog, PlatformReport, PlatformSetting


@admin.register(HomepageBanner)
class HomepageBannerAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'event', 'display_order', 'is_active', 'active_from', 'active_until')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'subtitle', 'event__title')


@admin.register(RecommendedEvent)
class RecommendedEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'priority_rank', 'is_active', 'start_date', 'end_date')
    list_filter = ('is_active',)
    search_fields = ('event__title',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'actor', 'action_type', 'target_model', 'target_id')
    list_filter = ('action_type', 'target_model', 'created_at')
    search_fields = ('actor__email', 'description', 'target_id')
    readonly_fields = ('actor', 'action_type', 'target_model', 'target_id', 'description', 'changes_payload', 'ip_address', 'created_at')


@admin.register(PlatformReport)
class PlatformReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'report_type', 'target_model', 'target_id', 'status', 'reporter', 'resolved_by')
    list_filter = ('status', 'report_type', 'target_model')
    search_fields = ('reason', 'details', 'target_id', 'reporter__email')


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'data_type', 'updated_at')
    search_fields = ('key', 'description')
