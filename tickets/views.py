from django.utils import timezone
from django.db.models import Q, Sum, Count
from rest_framework import status, views, permissions
from rest_framework.response import Response

from accounts.permissions import IsManagerUser
from .models import Order, AttendeeTicket
from .serializers import (
    OrderSerializer,
    AttendeeTicketSerializer,
    CheckoutSerializer,
)
from events.models import Event, TicketTier
from .paypal import create_paypal_order, capture_paypal_order


class CheckoutView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        if serializer.is_valid():
            order = serializer.save(user=request.user)
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserOrdersListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user)
        return Response(OrderSerializer(orders, many=True).data)


class UserTicketsListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get('status')
        tickets = AttendeeTicket.objects.filter(order__user=request.user).select_related('order', 'event', 'tier')

        now = timezone.localtime(timezone.now()) if timezone.is_aware(timezone.now()) else timezone.now()
        current_date = now.date()
        current_time = now.time()

        if status_filter == 'upcoming':
            tickets = tickets.filter(
                Q(event__status='published') & (
                    Q(event__date__gt=current_date) |
                    Q(event__date=current_date, event__end_time__isnull=False, event__end_time__gt=current_time) |
                    Q(event__date=current_date, event__end_time__isnull=True, event__start_time__gte=current_time)
                )
            )
        elif status_filter == 'past':
            tickets = tickets.filter(
                Q(event__status='past') |
                (
                    Q(event__status='published') & (
                        Q(event__date__lt=current_date) |
                        Q(event__date=current_date, event__end_time__isnull=False, event__end_time__lte=current_time) |
                        Q(event__date=current_date, event__end_time__isnull=True, event__start_time__lt=current_time)
                    )
                )
            )

        return Response(AttendeeTicketSerializer(tickets, many=True, context={'request': request}).data)


class ManagerTicketSalesView(views.APIView):
    permission_classes = [IsManagerUser]

    def get(self, request):
        manager_events = Event.objects.filter(organizer=request.user)
        events_list = [{'id': e.id, 'title': e.title} for e in manager_events]

        selected_events = manager_events
        event_filter = request.query_params.get('event')
        if event_filter and event_filter != 'all':
            if str(event_filter).isdigit():
                selected_events = manager_events.filter(pk=int(event_filter))
            else:
                selected_events = manager_events.filter(title__icontains=event_filter)

        orders = Order.objects.filter(event__in=selected_events)

        search = request.query_params.get('search')
        if search:
            orders = orders.filter(
                Q(order_number__icontains=search) |
                Q(user__full_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(event__title__icontains=search) |
                Q(tier__name__icontains=search)
            )

        # Calculate financial metrics
        confirmed_orders_qs = orders.filter(status__in=['Confirmed', 'Paid', 'Completed'])
        refunded_orders_qs = orders.filter(status='Refunded')

        total_gross = confirmed_orders_qs.aggregate(total=Sum('total_amount'))['total'] or 0.00
        confirmed_count = confirmed_orders_qs.count()
        refunds_total = refunded_orders_qs.aggregate(total=Sum('total_amount'))['total'] or 0.00
        refunds_count = refunded_orders_qs.count()
        total_tickets_sold = confirmed_orders_qs.aggregate(qty=Sum('quantity'))['qty'] or 0

        avg_order_value = (float(total_gross) / confirmed_count) if confirmed_count > 0 else 0.00
        avg_tickets_per_order = (float(total_tickets_sold) / confirmed_count) if confirmed_count > 0 else 0.0

        total_orders_attempted = confirmed_count + refunds_count
        success_rate = round((confirmed_count / (total_orders_attempted or 1)) * 100, 1)

        # Tier breakdown
        tiers = TicketTier.objects.filter(event__in=selected_events)
        tier_breakdown = []
        for t in tiers:
            tier_status = (
                "Sold Out" if t.sold_count >= t.capacity
                else ("Almost Full" if t.sold_count >= t.capacity * 0.8 else "Open")
            )
            tier_breakdown.append({
                'name': t.name,
                'event': t.event.title,
                'sold': t.sold_count,
                'total': t.capacity,
                'price': f"${t.price:,.2f}",
                'revenue': f"${(t.price * t.sold_count):,.2f}",
                'status': tier_status,
            })

        metrics = [
            {
                'label': 'Total Ticket Gross',
                'value': f"${total_gross:,.2f}",
                'sub': f"Across {selected_events.count()} event{'s' if selected_events.count() != 1 else ''}",
            },
            {
                'label': 'Confirmed Orders',
                'value': str(confirmed_count),
                'sub': f"{success_rate}% success rate",
            },
            {
                'label': 'Avg. Order Value',
                'value': f"${avg_order_value:,.2f}",
                'sub': f"{avg_tickets_per_order:.1f} tickets/order" if confirmed_count > 0 else "0.0 tickets/order",
            },
            {
                'label': 'Refunds / Disputed',
                'value': f"${refunds_total:,.2f}",
                'sub': f"{refunds_count} total refund request{'s' if refunds_count != 1 else ''}",
            },
        ]

        return Response({
            'metrics': metrics,
            'tierBreakdown': tier_breakdown,
            'transactions': OrderSerializer(orders, many=True).data,
            'events': events_list,
        })


class ManagerAttendeesView(views.APIView):
    permission_classes = [IsManagerUser]

    def get(self, request):
        from events.models import EventStaff

        # 1. Events organized by this manager
        owned_events = Event.objects.filter(organizer=request.user)

        # 2. Events where this manager is assigned as staff with can_view_attendees=True
        staff_event_ids = EventStaff.objects.filter(
            user=request.user,
            can_view_attendees=True
        ).values_list('event_id', flat=True)
        staff_events = Event.objects.filter(id__in=staff_event_ids).exclude(organizer=request.user)

        events_list = []
        for e in owned_events:
            events_list.append({'id': e.id, 'title': e.title, 'role': 'Organizer'})
        for e in staff_events:
            events_list.append({'id': e.id, 'title': f"{e.title} (Staff)", 'role': 'Staff'})

        all_accessible_events = (owned_events | staff_events).distinct()

        base_attendees = AttendeeTicket.objects.filter(event__in=all_accessible_events).select_related('event', 'tier', 'order')
        attendees = base_attendees

        event_filter = request.query_params.get('event')
        if event_filter and event_filter != 'all':
            if str(event_filter).isdigit():
                attendees = attendees.filter(event__id=int(event_filter))
                scoped_base = base_attendees.filter(event__id=int(event_filter))
            else:
                attendees = attendees.filter(event__title__icontains=event_filter)
                scoped_base = base_attendees.filter(event__title__icontains=event_filter)
        else:
            scoped_base = base_attendees

        status_filter = request.query_params.get('status', 'all')
        if status_filter == 'checked_in':
            attendees = attendees.filter(is_checked_in=True)
        elif status_filter == 'pending':
            attendees = attendees.filter(is_checked_in=False)

        search = request.query_params.get('search')
        if search:
            attendees = attendees.filter(
                Q(attendee_name__icontains=search) |
                Q(attendee_email__icontains=search) |
                Q(ticket_code__icontains=search)
            )

        total_registered = scoped_base.count()
        total_checked_in = scoped_base.filter(is_checked_in=True).count()
        total_pending = total_registered - total_checked_in
        check_in_rate = round((total_checked_in / (total_registered or 1)) * 100)

        return Response({
            'summary': {
                'totalRegistered': total_registered,
                'totalCheckedIn': total_checked_in,
                'totalPending': total_pending,
                'checkInRate': check_in_rate,
            },
            'attendees': AttendeeTicketSerializer(attendees, many=True).data,
            'events': events_list,
        })


class GateCheckInToggleView(views.APIView):
    permission_classes = [IsManagerUser]

    def _toggle_ticket(self, request, ticket_id):
        from events.permissions import check_event_staff_permission

        # Support lookup by pk or ticket_code
        if str(ticket_id).isdigit():
            ticket = AttendeeTicket.objects.filter(
                Q(pk=int(ticket_id)) | Q(ticket_code=ticket_id)
            ).select_related('event').first()
        else:
            ticket = AttendeeTicket.objects.filter(
                ticket_code=ticket_id
            ).select_related('event').first()

        if not ticket:
            return Response({'detail': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Check authorization: user must be event organizer OR assigned staff with can_check_in permission
        is_owner = (ticket.event.organizer_id == request.user.id)
        is_staff_checker = check_event_staff_permission(request.user, ticket.event, 'can_check_in')

        if not (is_owner or is_staff_checker):
            return Response(
                {'detail': 'You do not have gate check-in permissions for this event.'},
                status=status.HTTP_403_FORBIDDEN
            )

        ticket.is_checked_in = not ticket.is_checked_in
        ticket.checked_in_at = timezone.now() if ticket.is_checked_in else None
        ticket.save()

        return Response({
            'id': ticket.ticket_code,
            'ticketCode': ticket.ticket_code,
            'checkedIn': ticket.is_checked_in,
            'is_checked_in': ticket.is_checked_in,
            'checkInTime': ticket.checked_in_at.strftime('%I:%M %p') if ticket.checked_in_at else None,
            'message': 'Attendee admitted to venue.' if ticket.is_checked_in else 'Gate admission revoked.',
        })

    def patch(self, request, ticket_id):
        return self._toggle_ticket(request, ticket_id)

    def post(self, request, ticket_id):
        return self._toggle_ticket(request, ticket_id)


# ==========================================
# STAFF ATTENDEES & GATE VALIDATION VIEWS
# ==========================================

class StaffEventAttendeesView(views.APIView):
    """
    Staff endpoint to view attendee guest list for an assigned event.
    Requires can_view_attendees permission.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, event_id):
        from events.permissions import check_event_staff_permission

        event = Event.objects.filter(pk=event_id).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not check_event_staff_permission(request.user, event, 'can_view_attendees'):
            return Response(
                {'detail': 'You do not have permission to view attendees for this event.'},
                status=status.HTTP_403_FORBIDDEN
            )

        base_attendees = AttendeeTicket.objects.filter(event=event).select_related('tier', 'order')
        attendees = base_attendees

        status_filter = request.query_params.get('status', 'all')
        if status_filter == 'checked_in':
            attendees = attendees.filter(is_checked_in=True)
        elif status_filter == 'pending':
            attendees = attendees.filter(is_checked_in=False)

        search = request.query_params.get('search')
        if search:
            attendees = attendees.filter(
                Q(attendee_name__icontains=search) |
                Q(attendee_email__icontains=search) |
                Q(ticket_code__icontains=search)
            )

        total_registered = base_attendees.count()
        total_checked_in = base_attendees.filter(is_checked_in=True).count()
        total_pending = total_registered - total_checked_in
        check_in_rate = round((total_checked_in / (total_registered or 1)) * 100)

        # Get staff user's explicit permissions for UI gating
        from events.models import EventStaff
        staff_rec = EventStaff.objects.filter(event=event, user=request.user).first()
        user_perms = {
            'can_view_attendees': True if (event.organizer == request.user or (staff_rec and staff_rec.can_view_attendees)) else False,
            'can_check_in': True if (event.organizer == request.user or (staff_rec and staff_rec.can_check_in)) else False,
            'can_edit_attendees': True if (event.organizer == request.user or (staff_rec and staff_rec.can_edit_attendees)) else False,
        }

        return Response({
            'event': {
                'id': event.id,
                'title': event.title,
                'date': str(event.date),
                'venue': event.venue_name,
                'city': event.city,
            },
            'permissions': user_perms,
            'summary': {
                'totalRegistered': total_registered,
                'totalCheckedIn': total_checked_in,
                'totalPending': total_pending,
                'checkInRate': check_in_rate,
            },
            'attendees': AttendeeTicketSerializer(attendees, many=True).data,
        })

    def patch(self, request, event_id, attendee_id):
        from events.permissions import check_event_staff_permission

        event = Event.objects.filter(pk=event_id).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not check_event_staff_permission(request.user, event, 'can_edit_attendees'):
            return Response(
                {'detail': 'You do not have permission to edit attendee details for this event.'},
                status=status.HTTP_403_FORBIDDEN
            )

        ticket = AttendeeTicket.objects.filter(pk=attendee_id, event=event).first()
        if not ticket:
            return Response({'detail': 'Attendee record not found for this event.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        if 'seat_or_gate' in data or 'seatOrGate' in data:
            ticket.seat_or_gate = data.get('seat_or_gate', data.get('seatOrGate'))
        if 'attendee_name' in data or 'attendeeName' in data:
            ticket.attendee_name = data.get('attendee_name', data.get('attendeeName'))
        if 'attendee_email' in data or 'attendeeEmail' in data:
            ticket.attendee_email = data.get('attendee_email', data.get('attendeeEmail'))

        ticket.save()
        return Response(AttendeeTicketSerializer(ticket).data)


class StaffGateCheckInToggleView(views.APIView):
    """
    Staff endpoint to toggle guest admission check-in status at gate.
    Requires can_check_in permission and strictly verifies event scoping.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _toggle_ticket(self, request, event_id, ticket_id):
        from events.permissions import check_event_staff_permission

        event = Event.objects.filter(pk=event_id).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not check_event_staff_permission(request.user, event, 'can_check_in'):
            return Response(
                {'detail': 'You do not have gate check-in permissions for this event.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if str(ticket_id).isdigit():
            ticket = AttendeeTicket.objects.filter(
                Q(pk=int(ticket_id)) | Q(ticket_code=ticket_id),
                event=event
            ).first()
        else:
            ticket = AttendeeTicket.objects.filter(
                ticket_code=ticket_id,
                event=event
            ).first()

        if not ticket:
            return Response({'detail': 'Ticket code not found for this event.'}, status=status.HTTP_404_NOT_FOUND)

        ticket.is_checked_in = not ticket.is_checked_in
        ticket.checked_in_at = timezone.now() if ticket.is_checked_in else None
        ticket.save()

        return Response({
            'id': ticket.ticket_code,
            'ticketCode': ticket.ticket_code,
            'checkedIn': ticket.is_checked_in,
            'is_checked_in': ticket.is_checked_in,
            'checkInTime': ticket.checked_in_at.strftime('%I:%M %p') if ticket.checked_in_at else None,
            'attendeeName': ticket.attendee_name,
            'tierName': ticket.tier.name if ticket.tier else 'General',
            'message': f"{ticket.attendee_name} admitted successfully." if ticket.is_checked_in else f"Check-in revoked for {ticket.attendee_name}.",
        })

    def patch(self, request, event_id, ticket_id):
        return self._toggle_ticket(request, event_id, ticket_id)

    def post(self, request, event_id, ticket_id):
        return self._toggle_ticket(request, event_id, ticket_id)


class PayPalConfigView(views.APIView):
    """
    Public configuration endpoint for frontend PayPal JS SDK.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        import os
        from django.conf import settings
        client_id = os.environ.get('PAYPAL_CLIENT_ID') or getattr(settings, 'PAYPAL_CLIENT_ID', 'sb')
        currency = os.environ.get('PAYPAL_CURRENCY') or getattr(settings, 'PAYPAL_CURRENCY', 'USD')
        mode = os.environ.get('PAYPAL_MODE') or getattr(settings, 'PAYPAL_MODE', 'sandbox')
        return Response({
            'clientId': client_id,
            'currency': currency,
            'mode': mode,
        })


class PayPalCreateOrderView(views.APIView):
    """
    Step 1 of 2-phase checkout: validates seats/tickets, holds seats for 10 min,
    creates pending Order, and generates a PayPal order via PayPal REST API.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from decimal import Decimal
        from django.conf import settings
        from django.db import transaction
        from datetime import timedelta
        from events.models import Seat

        event_id = request.data.get('eventId') or request.data.get('event_id')
        tier_id = request.data.get('tierId') or request.data.get('tier_id')
        seat_ids = request.data.get('seatIds') or request.data.get('seat_ids') or []
        quantity = int(request.data.get('quantity', 1))
        attendee_name = request.data.get('attendeeName') or getattr(request.user, 'full_name', '') or 'Guest Attendee'
        attendee_email = request.data.get('attendeeEmail') or request.user.email

        if not event_id:
            return Response({'detail': 'Event ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        event = Event.objects.filter(pk=event_id).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        if event.status == 'draft':
            return Response({'detail': 'This event is not published.'}, status=status.HTTP_400_BAD_REQUEST)

        if event.is_ended or event.status == 'past':
            return Response({'detail': 'This event has ended.'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        hold_expiry = now + timedelta(minutes=10)

        with transaction.atomic():
            if seat_ids:
                # Lock rows to prevent simultaneous reservation
                locked_seats = list(
                    Seat.objects.select_for_update().filter(id__in=seat_ids, event=event).select_related('tier')
                )
                if len(locked_seats) != len(seat_ids):
                    return Response({'detail': 'One or more selected seats could not be found.'}, status=status.HTTP_400_BAD_REQUEST)

                for s in locked_seats:
                    # Seat is available if status is available OR reserved but expired
                    is_available = (s.status == 'available') or (s.status == 'reserved' and s.reserved_until and s.reserved_until < now)
                    if not is_available and s.reserved_by != request.user:
                        return Response({
                            'detail': f"Seat {s.row}-{s.seat_number} is currently held by another attendee. Please choose different seats."
                        }, status=status.HTTP_400_BAD_REQUEST)

                first_seat = locked_seats[0]
                tier = first_seat.tier or event.tiers.first()
                if not tier:
                    return Response({'detail': 'No ticket tier configured for this event.'}, status=status.HTTP_400_BAD_REQUEST)

                subtotal = sum((s.tier.price if s.tier else tier.price) for s in locked_seats)
                quantity = len(locked_seats)
                unit_price = (subtotal / quantity) if quantity > 0 else tier.price
                pass_fee = getattr(event, 'pass_platform_fee_to_buyer', True)
                fees = (subtotal * Decimal('0.035')).quantize(Decimal('0.01')) if (pass_fee and subtotal > 0) else Decimal('0.00')
                total_amount = subtotal + fees

                order = Order.objects.create(
                    user=request.user,
                    event=event,
                    tier=tier,
                    quantity=quantity,
                    unit_price=unit_price,
                    fees=fees,
                    total_amount=total_amount,
                    payment_method='PayPal (Sandbox)',
                    status='Pending'
                )

                # Hold the seats for 10 minutes
                for s in locked_seats:
                    s.status = 'reserved'
                    s.reserved_until = hold_expiry
                    s.reserved_by = request.user
                    s.order = order
                    s.save()

            else:
                if not tier_id:
                    return Response({'detail': 'Ticket tier ID is required.'}, status=status.HTTP_400_BAD_REQUEST)
                tier = TicketTier.objects.select_for_update().filter(pk=tier_id, event=event).first()
                if not tier:
                    return Response({'detail': 'Ticket tier not found.'}, status=status.HTTP_404_NOT_FOUND)

                remaining = tier.capacity - tier.sold_count
                if quantity > remaining:
                    return Response({'detail': f"Only {remaining} tickets remaining in this tier."}, status=status.HTTP_400_BAD_REQUEST)

                unit_price = tier.price
                subtotal = unit_price * quantity
                pass_fee = getattr(event, 'pass_platform_fee_to_buyer', True)
                fees = (subtotal * Decimal('0.035')).quantize(Decimal('0.01')) if (pass_fee and subtotal > 0) else Decimal('0.00')
                total_amount = subtotal + fees

                order = Order.objects.create(
                    user=request.user,
                    event=event,
                    tier=tier,
                    quantity=quantity,
                    unit_price=unit_price,
                    fees=fees,
                    total_amount=total_amount,
                    payment_method='PayPal (Sandbox)',
                    status='Pending'
                )

        # Call PayPal API to create PayPal order
        currency = getattr(settings, 'PAYPAL_CURRENCY', 'USD')
        try:
            paypal_data = create_paypal_order(
                amount=total_amount,
                currency=currency,
                custom_id=order.order_number,
                description=f"Tickets for {event.title}"
            )
            paypal_order_id = paypal_data.get('id')
            order.paypal_order_id = paypal_order_id
            order.save(update_fields=['paypal_order_id'])

            return Response({
                'paypalOrderId': paypal_order_id,
                'orderId': order.id,
                'orderNumber': order.order_number,
                'totalAmount': str(order.total_amount),
                'currency': currency,
                'expiresAt': hold_expiry.isoformat(),
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            # If PayPal API fails, cancel the order and release seats immediately
            with transaction.atomic():
                order.status = 'Failed'
                order.save(update_fields=['status'])
                Seat.objects.filter(order=order, status='reserved').update(
                    status='available',
                    reserved_until=None,
                    reserved_by=None,
                    order=None
                )
            return Response({'detail': f"Could not create PayPal checkout session: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PayPalCaptureOrderView(views.APIView):
    """
    Step 2 of 2-phase checkout: captures the PayPal payment, confirms the order,
    converts reserved seats to booked, and issues attendee tickets.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.db import transaction
        from .serializers import OrderSerializer
        from events.models import Seat

        order_id = request.data.get('orderId') or request.data.get('order_id')
        paypal_order_id = request.data.get('paypalOrderId') or request.data.get('paypal_order_id')
        attendee_name = request.data.get('attendeeName') or getattr(request.user, 'full_name', '') or 'Guest Attendee'
        attendee_email = request.data.get('attendeeEmail') or request.user.email

        if not order_id and not paypal_order_id:
            return Response({'detail': 'Order ID or PayPal Order ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        query = Order.objects.filter(user=request.user)
        if order_id:
            query = query.filter(pk=order_id)
        if paypal_order_id:
            query = query.filter(paypal_order_id=paypal_order_id)

        order = query.first()
        if not order:
            return Response({'detail': 'Pending order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status in ['Confirmed', 'Paid']:
            return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)

        paypal_id_to_capture = paypal_order_id or order.paypal_order_id
        if not paypal_id_to_capture:
            return Response({'detail': 'PayPal Order ID missing from transaction.'}, status=status.HTTP_400_BAD_REQUEST)

        # Execute PayPal capture
        try:
            capture_res = capture_paypal_order(paypal_id_to_capture)
            capture_status = capture_res.get('status')
            
            # Locate capture id inside purchase_units
            capture_id = None
            try:
                purchase_units = capture_res.get('purchase_units', [])
                if purchase_units:
                    payments = purchase_units[0].get('payments', {})
                    captures = payments.get('captures', [])
                    if captures:
                        capture_id = captures[0].get('id')
            except Exception:
                capture_id = None

            if capture_status == 'COMPLETED':
                with transaction.atomic():
                    order.status = 'Confirmed'
                    order.paypal_capture_id = capture_id or paypal_id_to_capture
                    order.save(update_fields=['status', 'paypal_capture_id'])

                    # Finalize reserved seats if any
                    reserved_seats = list(Seat.objects.select_for_update().filter(order=order))
                    tier_counts = {}

                    if reserved_seats:
                        for i, seat in enumerate(reserved_seats):
                            seat_tier = seat.tier or order.tier
                            ticket = AttendeeTicket.objects.create(
                                order=order,
                                event=order.event,
                                tier=seat_tier,
                                attendee_name=f"{attendee_name} #{i+1}" if len(reserved_seats) > 1 else attendee_name,
                                attendee_email=attendee_email,
                                seat_or_gate=f"Row {seat.row} • Seat {seat.seat_number}"
                            )
                            seat.status = 'booked'
                            seat.booked_by = request.user
                            seat.reserved_until = None
                            seat.reserved_by = None
                            seat.ticket = ticket
                            seat.save()

                            tier_counts[seat_tier.id] = tier_counts.get(seat_tier.id, 0) + 1

                    else:
                        # Non-assigned seating tickets
                        for i in range(order.quantity):
                            AttendeeTicket.objects.create(
                                order=order,
                                event=order.event,
                                tier=order.tier,
                                attendee_name=f"{attendee_name} #{i+1}" if order.quantity > 1 else attendee_name,
                                attendee_email=attendee_email,
                                seat_or_gate='Main Gate'
                            )
                        tier_counts[order.tier.id] = order.quantity

                    # Update sold counts
                    for t_id, cnt in tier_counts.items():
                        t_obj = TicketTier.objects.select_for_update().get(pk=t_id)
                        t_obj.sold_count += cnt
                        t_obj.save()

                return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)

            else:
                # Capture failed or pending
                with transaction.atomic():
                    order.status = 'Failed'
                    order.save(update_fields=['status'])
                    Seat.objects.filter(order=order, status='reserved').update(
                        status='available',
                        reserved_until=None,
                        reserved_by=None,
                        order=None
                    )
                return Response({'detail': f"Payment capture status: {capture_status}. Order was not completed."}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            with transaction.atomic():
                order.status = 'Failed'
                order.save(update_fields=['status'])
                Seat.objects.filter(order=order, status='reserved').update(
                    status='available',
                    reserved_until=None,
                    reserved_by=None,
                    order=None
                )
            return Response({'detail': f"PayPal capture failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


class PayPalCancelOrderView(views.APIView):
    """
    Cancel a pending order and release all held seats back to available.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.db import transaction
        from events.models import Seat

        order_id = request.data.get('orderId') or request.data.get('order_id')
        paypal_order_id = request.data.get('paypalOrderId') or request.data.get('paypal_order_id')

        query = Order.objects.filter(user=request.user, status='Pending')
        if order_id:
            query = query.filter(pk=order_id)
        elif paypal_order_id:
            query = query.filter(paypal_order_id=paypal_order_id)

        order = query.first()
        if not order:
            return Response({'detail': 'No pending order found to cancel.'}, status=status.HTTP_200_OK)

        with transaction.atomic():
            order.status = 'Cancelled'
            order.save(update_fields=['status'])
            Seat.objects.filter(order=order, status='reserved').update(
                status='available',
                reserved_until=None,
                reserved_by=None,
                order=None
            )

        return Response({'detail': 'Order cancelled and seat reservations released.'}, status=status.HTTP_200_OK)


