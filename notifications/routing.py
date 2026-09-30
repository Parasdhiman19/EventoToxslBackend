"""
Notification WebSocket URL routing.
Mounts at: ws://localhost:8000/ws/notifications/
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]
