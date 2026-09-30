"""
Evento ASGI Configuration
==========================
Replaces wsgi.py to enable Django Channels WebSocket support alongside
the standard Django HTTP REST API.

Routing:
  - HTTP  → Django's standard URL resolver (all existing REST endpoints)
  - WS    → Django Channels routing (WebSocket connections)
"""

import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'EvnetoBackend.settings')

# Initialize Django BEFORE importing anything that depends on apps being loaded
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # All standard HTTP traffic goes to Django's ASGI app
    'http': get_asgi_application(),

    # WebSocket traffic is routed through Channels
    # Note: JWT auth middleware is applied inside the consumer itself
    # so plain URLRouter is sufficient here
    'websocket': URLRouter(websocket_urlpatterns),
})
