"""
Notification REST API Views
============================

All views strictly enforce recipient == request.user.
Users can NEVER access, modify, or delete another user's notifications.

Endpoints:
  GET    /api/notifications/                 → Paginated list
  GET    /api/notifications/unread-count/    → Lightweight badge count
  PATCH  /api/notifications/<id>/read/       → Mark single as read
  PATCH  /api/notifications/<id>/unread/     → Mark single as unread
  POST   /api/notifications/mark-all-read/   → Mark all as read
  DELETE /api/notifications/<id>/            → Dismiss single notification
"""

from rest_framework import views, status, permissions
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Notification
from .serializers import NotificationSerializer


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


class NotificationListView(views.APIView):
    """
    GET /api/notifications/
    Returns paginated notifications for the authenticated user.
    Supports ?filter=all (default) or ?filter=unread
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filter_param = request.query_params.get('filter', 'all')
        qs = Notification.objects.filter(recipient=request.user).select_related(
            'actor', 'event', 'order', 'ticket'
        )

        if filter_param == 'unread':
            qs = qs.filter(is_read=False)

        paginator = NotificationPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = NotificationSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


class UnreadCountView(views.APIView):
    """
    GET /api/notifications/unread-count/
    Returns a lightweight unread count — used by the notification bell badge.
    This endpoint is designed to be polled as a fallback when WebSocket is disconnected.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({'unreadCount': count})


class NotificationMarkReadView(views.APIView):
    """
    PATCH /api/notifications/<id>/read/
    Mark a single notification as read. Strictly scoped to request.user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        notif = Notification.objects.filter(pk=pk, recipient=request.user).first()
        if not notif:
            return Response({'detail': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
        notif.mark_as_read()
        return Response(NotificationSerializer(notif).data)


class NotificationMarkUnreadView(views.APIView):
    """
    PATCH /api/notifications/<id>/unread/
    Mark a single notification as unread.
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        notif = Notification.objects.filter(pk=pk, recipient=request.user).first()
        if not notif:
            return Response({'detail': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
        notif.mark_as_unread()

        # Push updated count to WebSocket
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer:
                unread_count = Notification.objects.filter(
                    recipient=request.user, is_read=False
                ).count()
                async_to_sync(channel_layer.group_send)(
                    f'notif_user_{request.user.id}',
                    {
                        'type': 'notification.read',
                        'notification_id': notif.id,
                        'unread_count': unread_count,
                    }
                )
        except Exception:
            pass

        return Response(NotificationSerializer(notif).data)


class NotificationMarkAllReadView(views.APIView):
    """
    POST /api/notifications/mark-all-read/
    Mark all unread notifications as read for request.user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.utils import timezone
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())

        # Push unread count reset to WebSocket
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f'notif_user_{request.user.id}',
                    {
                        'type': 'notification.read',
                        'notification_id': None,
                        'unread_count': 0,
                    }
                )
        except Exception:
            pass

        return Response({'marked': updated, 'unreadCount': 0})


class NotificationDeleteView(views.APIView):
    """
    DELETE /api/notifications/<id>/
    Dismiss (permanently delete) a single notification. Scoped to request.user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        notif = Notification.objects.filter(pk=pk, recipient=request.user).first()
        if not notif:
            return Response({'detail': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
        notif.delete()
        return Response({'deleted': True, 'id': pk}, status=status.HTTP_200_OK)
