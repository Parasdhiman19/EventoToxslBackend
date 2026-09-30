from django.urls import path
from .views import (
    AdminDashboardStatsView,
    AdminRecentActivityView,
    AdminBannerListCreateView,
    AdminBannerDetailView,
    AdminBannerReorderView,
    AdminRecommendedEventListCreateView,
    AdminRecommendedEventDetailView,
    AdminRecommendedEventReorderView,
    AdminEventListView,
    AdminEventDetailView,
    AdminEventStatusView,
    AdminEventToggleFeaturedView,
    AdminUserListView,
    AdminUserSuspendView,
    AdminUserUnsuspendView,
    AdminUserRoleView,
    AdminOrganizerListView,
    AdminTransactionListView,
    AdminPayoutListView,
    AdminPayoutProcessView,
    AdminAttendanceListView,
    AdminPlatformReportListView,
    AdminPlatformReportDetailView,
    AdminPlatformSettingsView,
    AdminAuditLogListView,
    PublicHomepageContentView,
)

urlpatterns = [
    # 1. Executive Dashboard & Real-Time Feed
    path('dashboard/stats/', AdminDashboardStatsView.as_view(), name='admin_dashboard_stats'),
    path('dashboard/activity/', AdminRecentActivityView.as_view(), name='admin_dashboard_activity'),

    # 2. Homepage Hero Banners
    path('banners/', AdminBannerListCreateView.as_view(), name='admin_banners_list_create'),
    path('banners/<int:pk>/', AdminBannerDetailView.as_view(), name='admin_banner_detail'),
    path('banners/reorder/', AdminBannerReorderView.as_view(), name='admin_banners_reorder'),

    # 3. Recommended Events
    path('recommended-events/', AdminRecommendedEventListCreateView.as_view(), name='admin_recommended_events'),
    path('recommended-events/<int:pk>/', AdminRecommendedEventDetailView.as_view(), name='admin_recommended_event_detail'),
    path('recommended-events/reorder/', AdminRecommendedEventReorderView.as_view(), name='admin_recommended_events_reorder'),

    # 4. Public Discovery Content (Homepage)
    path('content/homepage/', PublicHomepageContentView.as_view(), name='public_homepage_content'),

    # 5. Events Oversight & Moderation
    path('events/', AdminEventListView.as_view(), name='admin_events_list'),
    path('events/<int:pk>/', AdminEventDetailView.as_view(), name='admin_event_detail'),
    path('events/<int:pk>/status/', AdminEventStatusView.as_view(), name='admin_event_status'),
    path('events/<int:pk>/toggle-featured/', AdminEventToggleFeaturedView.as_view(), name='admin_event_toggle_featured'),

    # 6. Users & Organizers
    path('users/', AdminUserListView.as_view(), name='admin_users_list'),
    path('users/<int:pk>/suspend/', AdminUserSuspendView.as_view(), name='admin_user_suspend'),
    path('users/<int:pk>/unsuspend/', AdminUserUnsuspendView.as_view(), name='admin_user_unsuspend'),
    path('users/<int:pk>/role/', AdminUserRoleView.as_view(), name='admin_user_role'),
    path('organizers/', AdminOrganizerListView.as_view(), name='admin_organizers_list'),

    # 7. Financial Transactions & Payout Approvals
    path('transactions/', AdminTransactionListView.as_view(), name='admin_transactions_list'),
    path('payouts/', AdminPayoutListView.as_view(), name='admin_payouts_list'),
    path('payouts/<int:pk>/process/', AdminPayoutProcessView.as_view(), name='admin_payout_process'),

    # 8. Attendance & Scanner Activity
    path('attendance/', AdminAttendanceListView.as_view(), name='admin_attendance_list'),

    # 9. Moderation Reports
    path('reports/', AdminPlatformReportListView.as_view(), name='admin_reports_list'),
    path('reports/<int:pk>/', AdminPlatformReportDetailView.as_view(), name='admin_report_detail'),

    # 10. Platform Settings & Audit Logs
    path('settings/', AdminPlatformSettingsView.as_view(), name='admin_platform_settings'),
    path('audit-logs/', AdminAuditLogListView.as_view(), name='admin_audit_logs'),
]
