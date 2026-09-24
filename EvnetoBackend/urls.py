"""
Evento Backend Root URL Configuration
====================================

This file defines the top-level URL routing hierarchy for the Evento API.
All application endpoints are modularized across feature-specific sub-routers:

Base URL Tree:
--------------
/admin/                  -> Django Administration Portal
/api/auth/               -> Authentication, User Profiles & Organizer Setup (accounts app)
/api/events/             -> Event Discovery, Creation, Social & Management (events app)
/api/tickets/            -> Ticket Sales, Checkout, PayPal & Gate Check-in (tickets app)
/api/payouts/            -> Revenue Analytics, Escrow & PayPal Disbursals (payouts app)
/media/                  -> User-uploaded static media files (served in DEBUG mode)

Authentication Model:
---------------------
- Public routes: accessible without credentials.
- Authenticated routes: require `Authorization: Bearer <access_token>` header.
- Manager routes: require user to have active organizer capabilities (`OrganizerProfile`).
- Staff routes: require user to be explicitly assigned to an event staff roster.
- JWT tokens: Short-lived Access Token (Header/Body) + Secure HttpOnly Refresh Cookie.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from events.views import ImageUploadView

urlpatterns = [
    # Universal Upload Endpoint
    path('api/upload/image/', ImageUploadView.as_view(), name='root_image_upload'),

    # -------------------------------------------------------------------------
    # 1. Django Admin Console
    # -------------------------------------------------------------------------
    # System administrator portal for database management and user maintenance.
    path('admin/', admin.site.urls),

    # -------------------------------------------------------------------------
    # 2. Authentication & User Accounts (/api/auth/) -> accounts/urls.py
    # -------------------------------------------------------------------------
    # Handles user registration, credentials login, JWT token refresh, logout,
    # current user identity ('me'), organizer profile activation & payout settings.
    path('api/auth/', include('accounts.urls')),

    # -------------------------------------------------------------------------
    # 3. Events & Discovery (/api/events/) -> events/urls.py
    # -------------------------------------------------------------------------
    # Handles public event listings, hero features, interactive seat maps,
    # social feeds (likes & threaded comments), organizer event creation/editing,
    # gate staff assignment, staff assignment portal, and attendee bookmarks.
    path('api/events/', include('events.urls')),

    # -------------------------------------------------------------------------
    # 4. Tickets, Checkout & Gate Admissions (/api/tickets/) -> tickets/urls.py
    # -------------------------------------------------------------------------
    # Handles direct checkout, PayPal sandbox integration (create/capture/cancel),
    # attendee ticket & order retrieval, QR pass generation, organizer sales analytics,
    # attendee roster search, and real-time gate check-in scanners.
    path('api/tickets/', include('tickets.urls')),

    # -------------------------------------------------------------------------
    # 5. Payouts & Financial Disbursements (/api/payouts/) -> payouts/urls.py
    # -------------------------------------------------------------------------
    # Handles organizer revenue overview, escrow calculations, PayPal payout method
    # management, and automated instant disbursements via PayPal Payouts REST API.
    path('api/payouts/', include('payouts.urls')),
]

# Serve user-uploaded media files (event banners, avatars, seat maps) during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

