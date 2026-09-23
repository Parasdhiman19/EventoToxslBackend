"""
Authentication & Accounts URL Configuration
===========================================

Base Prefix: /api/auth/

Endpoints:
----------
POST   /signup/                -> Register new account + return JWT tokens (public)
POST   /login/                 -> Authenticate user credentials + return JWT tokens (public)
POST   /token/refresh/         -> Refresh JWT access token from HttpOnly cookie (public)
POST   /logout/                -> Invalidate / clear HttpOnly refresh cookie (public)
GET    /me/                    -> Retrieve current authenticated user profile (auth)
POST   /become-organizer/      -> Activate organizer capabilities for user (auth)
GET    /settings/              -> Get organizer profile & settlement settings (manager)
PATCH  /settings/              -> Update organizer profile details (manager)
GET    /settlement-accounts/   -> List connected payout bank/PayPal accounts (manager)
POST   /settlement-accounts/   -> Add a new settlement payout account (manager)
"""

from django.urls import path
from .views import (
    SignupView,
    LoginView,
    CustomTokenRefreshView,
    LogoutView,
    MeView,
    BecomeOrganizerView,
    OrganizerSettingsView,
    SettlementAccountListView,
    SettlementAccountDetailView,
    StudioStaffListView,
    StudioStaffDetailView,
)

urlpatterns = [
    # -------------------------------------------------------------------------
    # Authentication & Session Management (Public)
    # -------------------------------------------------------------------------
    # POST: Registers a new user with email/password/name, sets refresh cookie & returns access token
    path('signup/', SignupView.as_view(), name='auth_signup'),

    # POST: Authenticates credentials, sets HttpOnly refresh cookie & returns access token + user info
    path('login/', LoginView.as_view(), name='auth_login'),

    # POST: Exchanges valid HttpOnly refresh cookie for a new short-lived JWT access token
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),

    # POST: Clears the HttpOnly refresh token cookie to log out the user session
    path('logout/', LogoutView.as_view(), name='auth_logout'),

    # -------------------------------------------------------------------------
    # User Profile & Organizer Onboarding (Authenticated)
    # -------------------------------------------------------------------------
    # GET: Returns current logged-in user profile, role, avatar, and organizer status
    path('me/', MeView.as_view(), name='auth_me'),

    # POST: Upgrades a standard user to an organizer by creating their OrganizerProfile
    path('become-organizer/', BecomeOrganizerView.as_view(), name='become_organizer'),

    # -------------------------------------------------------------------------
    # Organizer Studio Settings & Settlement Accounts (Manager/Organizer Only)
    # -------------------------------------------------------------------------
    # GET: Retrieves organizer profile details & settlement accounts
    # PATCH: Updates organizer studio name, bio, social media handles, support email
    path('settings/', OrganizerSettingsView.as_view(), name='organizer_settings'),

    # GET: Lists all connected payout settlement accounts (e.g. PayPal, Bank)
    # POST: Creates/connects a new payout settlement account for ticket disbursements
    path('settlement-accounts/', SettlementAccountListView.as_view(), name='settlement_accounts'),
    path('settlement-accounts/<int:pk>/', SettlementAccountDetailView.as_view(), name='settlement_account_detail'),

    # -------------------------------------------------------------------------
    # Studio Team & Staff Directory (Manager/Organizer Only)
    # -------------------------------------------------------------------------
    # GET: Lists all saved studio staff members in organizer's team directory
    # POST: Adds/invites a user to the organizer's studio staff roster
    path('studio-staff/', StudioStaffListView.as_view(), name='studio_staff_list'),
    path('studio-staff/<int:pk>/', StudioStaffDetailView.as_view(), name='studio_staff_detail'),
]

