"""
Tickets, Checkout & Gate Operations URL Configuration
======================================================

Base Prefix: /api/tickets/

Endpoints Summary:
------------------
1. User / Attendee Ticket Actions:
   POST   /checkout/                                                 -> Process direct/mock ticket purchase + generate passes (auth)
   GET    /user/orders/                                              -> List authenticated user purchase & order history (auth)
   GET    /user/passes/                                              -> List attendee ticket passes with QR codes (auth, ?status=upcoming|past)

2. PayPal Sandbox Checkout Flow:
   GET    /paypal/config/                                            -> Retrieve PayPal client ID & environment settings (public)
   POST   /paypal/create-order/                                      -> Create an order in PayPal Sandbox API (auth)
   POST   /paypal/capture-order/                                     -> Capture payment, finalize order & issue ticket passes (auth)
   POST   /paypal/cancel-order/                                      -> Handle cancellation during PayPal checkout flow (auth)

3. Organizer / Manager Operations:
   GET    /manager/sales/                                            -> Retrieve ticket sales revenue, volume & order breakdowns (manager)
   GET    /manager/attendees/                                        -> Search & list all ticket holders across manager events (manager)
   POST   /manager/attendees/<str:ticket_id>/check-in/               -> Toggle gate admission / check-in status for an attendee pass (manager)

4. Staff Gate Scanning Operations:
   GET    /staff/events/<int:event_id>/attendees/                    -> List attendee roster for an assigned event (staff/manager)
   GET    /staff/events/<int:event_id>/attendees/<int:attendee_id>/  -> Retrieve specific attendee verification details (staff/manager)
   POST   /staff/events/<int:event_id>/attendees/<str:ticket_id>/check-in/ -> Validate & check in attendee pass via QR/UUID (staff/manager)
"""

from django.urls import path
from .views import (
    CheckoutView,
    UserOrdersListView,
    UserTicketsListView,
    ManagerTicketSalesView,
    ManagerAttendeesView,
    GateCheckInToggleView,
    StaffEventAttendeesView,
    StaffGateCheckInToggleView,
    PayPalConfigView,
    PayPalCreateOrderView,
    PayPalCaptureOrderView,
    PayPalCancelOrderView,
)

urlpatterns = [
    # -------------------------------------------------------------------------
    # 1. User / Attendee Ticket Actions (Authenticated)
    # -------------------------------------------------------------------------
    # POST: Completes ticket purchase, reserves seats, decrements tier capacity, and generates QR passes
    path('checkout/', CheckoutView.as_view(), name='tickets_checkout'),

    # GET: Returns user's complete order history with total amounts, payment methods, and invoice status
    path('user/orders/', UserOrdersListView.as_view(), name='user_orders'),

    # GET: Returns all attendee ticket passes (supports ?status=upcoming or ?status=past) including QR code payloads
    path('user/passes/', UserTicketsListView.as_view(), name='user_tickets'),

    # -------------------------------------------------------------------------
    # 2. PayPal Sandbox Integration Endpoints
    # -------------------------------------------------------------------------
    # GET: Returns PayPal Client ID and currency configuration for frontend PayPal Buttons SDK
    path('paypal/config/', PayPalConfigView.as_view(), name='paypal_config'),

    # POST: Initializes a PayPal transaction order with line items, tier pricing, and seat holds
    path('paypal/create-order/', PayPalCreateOrderView.as_view(), name='paypal_create_order'),

    # POST: Captures authorized PayPal payment, validates funds, creates Order and AttendeeTicket records
    path('paypal/capture-order/', PayPalCaptureOrderView.as_view(), name='paypal_capture_order'),

    # POST: Handles cancelled checkout sessions and releases temporary seat reservations
    path('paypal/cancel-order/', PayPalCancelOrderView.as_view(), name='paypal_cancel_order'),

    # -------------------------------------------------------------------------
    # 3. Manager Ticket Sales & Gate Admissions (Organizer Only - IsManagerUser)
    # -------------------------------------------------------------------------
    # GET: Aggregates total sales, ticket volumes, refund metrics, and recent transactions (?event=<id|all>, ?search=)
    path('manager/sales/', ManagerTicketSalesView.as_view(), name='manager_ticket_sales'),

    # GET: Lists all attendees across organizer's events with check-in timestamps, seat numbers, and tier info
    path('manager/attendees/', ManagerAttendeesView.as_view(), name='manager_attendees'),

    # POST: Toggles check-in state (Admitted vs Not Checked-In) for a ticket pass via ticket UUID or scanned QR code
    path('manager/attendees/<str:ticket_id>/check-in/', GateCheckInToggleView.as_view(), name='gate_check_in_toggle'),

    # -------------------------------------------------------------------------
    # 4. Staff Gate Scanning & Attendee Verification (Staff Assigned / Manager)
    # -------------------------------------------------------------------------
    # GET: Retrieves attendee list for gate scanners working on a specific assigned event
    path('staff/events/<int:event_id>/attendees/', StaffEventAttendeesView.as_view(), name='staff_event_attendees'),

    # GET: Fetches single attendee verification details for gate support
    path('staff/events/<int:event_id>/attendees/<int:attendee_id>/', StaffEventAttendeesView.as_view(), name='staff_event_attendee_detail'),

    # POST: Validates ticket QR / UUID code at the entry gate and marks pass as checked-in
    path('staff/events/<int:event_id>/attendees/<str:ticket_id>/check-in/', StaffGateCheckInToggleView.as_view(), name='staff_gate_check_in_toggle'),
]


