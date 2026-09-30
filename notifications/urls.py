"""
Notification REST URL Configuration
Mounted at: /api/notifications/
"""

from django.urls import path
from . import views

urlpatterns = [
    # List (paginated)
    path('', views.NotificationListView.as_view(), name='notification-list'),

    # Lightweight badge count
    path('unread-count/', views.UnreadCountView.as_view(), name='notification-unread-count'),

    # Bulk mark all as read
    path('mark-all-read/', views.NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),

    # Single notification actions
    path('<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('<int:pk>/unread/', views.NotificationMarkUnreadView.as_view(), name='notification-mark-unread'),
    path('<int:pk>/delete/', views.NotificationDeleteView.as_view(), name='notification-delete'),
]
