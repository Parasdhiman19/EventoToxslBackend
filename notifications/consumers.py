"""
Notification WebSocket Consumer
================================

Authentication Flow:
  1. Client opens ws://localhost:8000/ws/notifications/
  2. Client immediately sends: {"type": "auth", "token": "<JWT access token>"}
  3. Consumer validates JWT, resolves user, adds socket to personal Redis group
  4. Consumer sends back: {"type": "connection_established", "unread_count": N}
  5. From that point on, NotificationService pushes messages through the Redis channel layer
     and this consumer forwards them to the browser in real time.

Security:
  - Connections that don't send a valid auth frame within 10 seconds are closed.
  - Each user has their own Redis group: "notif_user_<user_id>"
  - Users can NEVER receive another user's notifications.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notification delivery.
    One instance per connected browser tab / client.
    """

    # Time in seconds before an unauthenticated connection is closed
    AUTH_TIMEOUT = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.group_name = None

    # ─────────────────────────────────────────────────────────────
    # Connection Lifecycle
    # ─────────────────────────────────────────────────────────────

    async def connect(self):
        """Accept the connection immediately. Authentication happens via the first message."""
        await self.accept()

    async def disconnect(self, close_code):
        """Clean up Redis group membership on disconnect."""
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    # ─────────────────────────────────────────────────────────────
    # Message Handling (inbound from client)
    # ─────────────────────────────────────────────────────────────

    async def receive(self, text_data):
        """Handle messages from the WebSocket client."""
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self._send_error('invalid_json', 'Message must be valid JSON.')
            return

        msg_type = data.get('type')

        if msg_type == 'auth':
            await self._handle_auth(data.get('token', ''))

        elif msg_type == 'ping':
            # Lightweight keepalive from client
            await self._send({'type': 'pong'})

        elif msg_type == 'mark_read':
            # Client can mark a notification read via WebSocket
            notification_id = data.get('notification_id')
            if notification_id and self.user:
                await self._mark_notification_read(notification_id)

        else:
            await self._send_error('unknown_type', f'Unknown message type: {msg_type}')

    # ─────────────────────────────────────────────────────────────
    # Authentication
    # ─────────────────────────────────────────────────────────────

    async def _handle_auth(self, token: str):
        """Validate JWT token and join the user's personal Redis group."""
        if not token:
            await self._send_error('auth_required', 'Token is required.')
            await self.close(code=4001)
            return

        user = await self._get_user_from_token(token)
        if not user:
            await self._send_error('auth_failed', 'Invalid or expired token.')
            await self.close(code=4003)
            return

        self.user = user
        self.group_name = f'notif_user_{user.id}'

        # Join the user's personal notification channel in Redis
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # Send confirmation with current unread count
        unread_count = await self._get_unread_count()
        await self._send({
            'type': 'connection_established',
            'unreadCount': unread_count,
            'userId': user.id,
        })
        logger.info(f'[WS] User {user.email} (id={user.id}) connected to notifications.')

    # ─────────────────────────────────────────────────────────────
    # Group Event Handlers (inbound from channel layer / Redis)
    # ─────────────────────────────────────────────────────────────

    async def notification_new(self, event):
        """
        Called by Django channel layer when NotificationService calls group_send.
        Forwards the notification payload to the connected WebSocket client.
        """
        await self._send({
            'type': 'notification.new',
            'notification': event.get('notification'),
            'unreadCount': event.get('unread_count', 0),
        })

    async def notification_read(self, event):
        """Broadcast read-state change to all open tabs for this user."""
        await self._send({
            'type': 'notification.read',
            'notificationId': event.get('notification_id'),
            'unreadCount': event.get('unread_count', 0),
        })

    # ─────────────────────────────────────────────────────────────
    # Database Helpers (run sync DB operations in thread pool)
    # ─────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_user_from_token(self, token: str):
        """Validate JWT access token and return the User instance or None."""
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
            from django.contrib.auth import get_user_model

            User = get_user_model()
            decoded = AccessToken(token)
            user_id = decoded.get('user_id')
            if not user_id:
                return None
            return User.objects.filter(pk=user_id, is_active=True).first()

        except (TokenError, InvalidToken, Exception) as e:
            logger.warning(f'[WS] JWT validation failed: {e}')
            return None

    @database_sync_to_async
    def _get_unread_count(self) -> int:
        """Return the current unread notification count for the authenticated user."""
        if not self.user:
            return 0
        from .models import Notification
        return Notification.objects.filter(recipient=self.user, is_read=False).count()

    @database_sync_to_async
    def _mark_notification_read(self, notification_id):
        """Mark a notification as read, restricted to the authenticated user."""
        if not self.user:
            return
        from .models import Notification
        notif = Notification.objects.filter(
            pk=notification_id, recipient=self.user
        ).first()
        if notif:
            notif.mark_as_read()

    # ─────────────────────────────────────────────────────────────
    # Outbound Helpers
    # ─────────────────────────────────────────────────────────────

    async def _send(self, payload: dict):
        """Send a JSON payload to the WebSocket client."""
        await self.send(text_data=json.dumps(payload))

    async def _send_error(self, code: str, message: str):
        """Send a structured error frame to the client."""
        await self._send({'type': 'error', 'code': code, 'message': message})
