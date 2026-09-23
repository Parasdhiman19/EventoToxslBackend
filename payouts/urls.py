"""
Payouts & Revenue Settlements URL Configuration
================================================

Base Prefix: /api/payouts/

Endpoints Summary:
------------------
1. Manager Analytics & Overview:
   GET    /manager/overview/           -> Aggregate dashboard revenue, tickets sold, attendance rate & recent transactions (manager)

2. Payout Balances & History:
   GET    /manager/payouts/            -> Available withdrawal balance, escrow breakdown, stage settlements & disbursement history (manager)

3. Settlement / Payout Methods:
   GET    /manager/methods/            -> List connected PayPal payout accounts (manager)
   POST   /manager/methods/            -> Add / connect a new PayPal payout email address (manager)
   PATCH  /manager/methods/<int:pk>/   -> Update payout method (e.g. set as primary) (manager)
   DELETE /manager/methods/<int:pk>/   -> Remove a connected payout method (manager)

4. Instant Payout Disbursals:
   POST   /manager/payouts/request/    -> Trigger instant fund transfer to PayPal via PayPal Payouts REST API (manager)
"""

from django.urls import path
from .views import (
    ManagerOverviewView,
    ManagerPayoutsView,
    ManagerPayoutMethodsView,
    ManagerPayoutMethodDetailView,
    RequestPayoutView,
)

urlpatterns = [
    # -------------------------------------------------------------------------
    # 1. Organizer Dashboard & Earnings Overview (Manager Only - IsManagerUser)
    # -------------------------------------------------------------------------
    # GET: Returns financial metrics (Gross Revenue, Tickets Sold, Attendance %, Active Stages, Recent Orders)
    path('manager/overview/', ManagerOverviewView.as_view(), name='manager_overview'),

    # -------------------------------------------------------------------------
    # 2. Payout Balances & Stage Settlement History (Manager Only - IsManagerUser)
    # -------------------------------------------------------------------------
    # GET: Returns available withdrawal balance, pending escrow funds, platform fee deductions, per-stage settlements & disbursement records
    path('manager/payouts/', ManagerPayoutsView.as_view(), name='manager_payouts'),

    # -------------------------------------------------------------------------
    # 3. Payout Destination Methods (Manager Only - IsManagerUser)
    # -------------------------------------------------------------------------
    # GET: Lists all connected PayPal withdrawal accounts
    # POST: Connects a new PayPal settlement account with automatic primary status assignment
    path('manager/methods/', ManagerPayoutMethodsView.as_view(), name='manager_payout_methods'),

    # PATCH: Updates payout method preferences (e.g., mark as default/primary)
    # DELETE: Removes payout method and promotes next available method to primary if needed
    path('manager/methods/<int:pk>/', ManagerPayoutMethodDetailView.as_view(), name='manager_payout_method_detail'),

    # -------------------------------------------------------------------------
    # 4. Instant Withdrawal / Disbursement Execution (Manager Only - IsManagerUser)
    # -------------------------------------------------------------------------
    # POST: Validates available funds and dispatches instant live payout via PayPal Payouts REST API to recipient's email
    path('manager/payouts/request/', RequestPayoutView.as_view(), name='request_payout'),
]


