from datetime import date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, OrganizerProfile
from accounts.constants import USER, MANAGER
from events.models import Event, TicketTier
from tickets.models import Order, AttendeeTicket


class TicketsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            email='organizer@evento.com',
            password='Password123!',
            full_name='Stage Master',
            role=MANAGER
        )
        self.org_profile = OrganizerProfile.objects.create(
            user=self.manager,
            organization_name='Master Productions',
        )
        self.attendee = User.objects.create_user(
            email='attendee@evento.com',
            password='Password123!',
            full_name='Event Attendee',
            role=USER
        )

        future_date = timezone.now().date() + timedelta(days=30)
        self.event = Event.objects.create(
            organizer=self.manager,
            title='Electronic Solstice 2026',
            category='Music & Concerts',
            date=future_date,
            start_time=time(20, 0),
            venue_name='Warehouse Stage',
            city='Chandigarh',
            status='published'
        )
        self.tier = TicketTier.objects.create(
            event=self.event,
            name='General Admission',
            price=Decimal('35.00'),
            capacity=100
        )

    def test_checkout_and_passes(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'attendee@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Checkout 2 tickets
        checkout_res = self.client.post('/api/tickets/checkout/', {
            'eventId': self.event.id,
            'tierId': self.tier.id,
            'quantity': 2,
            'paymentMethod': 'UPI • Axis Bank',
            'attendeeName': 'Event Attendee'
        }, format='json')
        self.assertEqual(checkout_res.status_code, status.HTTP_201_CREATED)
        self.tier.refresh_from_db()
        self.assertEqual(self.tier.sold_count, 2)

        # Get user orders
        orders_res = self.client.get('/api/tickets/user/orders/')
        self.assertEqual(orders_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(orders_res.data), 1)

        # Get user passes
        passes_res = self.client.get('/api/tickets/user/passes/')
        self.assertEqual(passes_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(passes_res.data), 2)

    def test_manager_sales_and_gate_check_in(self):
        # Create an order first
        order = Order.objects.create(
            user=self.attendee,
            event=self.event,
            tier=self.tier,
            quantity=1,
            unit_price=self.tier.price,
            fees=Decimal('1.20'),
            total_amount=Decimal('36.20'),
            status='Confirmed'
        )
        ticket = AttendeeTicket.objects.create(
            order=order,
            event=self.event,
            tier=self.tier,
            attendee_name='Event Attendee',
            attendee_email=self.attendee.email
        )

        # Login as manager
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # View manager sales
        sales_res = self.client.get('/api/tickets/manager/sales/')
        self.assertEqual(sales_res.status_code, status.HTTP_200_OK)
        self.assertIn('metrics', sales_res.data)
        self.assertEqual(len(sales_res.data['transactions']), 1)

        # View manager attendees
        attendees_res = self.client.get('/api/tickets/manager/attendees/')
        self.assertEqual(attendees_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(attendees_res.data['attendees']), 1)

        # Toggle gate check-in
        check_in_res = self.client.patch(f'/api/tickets/manager/attendees/{ticket.ticket_code}/check-in/')
        self.assertEqual(check_in_res.status_code, status.HTTP_200_OK)
        self.assertTrue(check_in_res.data['checkedIn'])

        ticket.refresh_from_db()
        self.assertTrue(ticket.is_checked_in)

    def test_staff_attendees_permissions_and_event_isolation(self):
        from events.models import EventStaff

        # Create a second event owned by another manager
        rival_manager = User.objects.create_user(
            email='rival@evento.com',
            password='Password123!',
            role=MANAGER
        )
        OrganizerProfile.objects.create(user=rival_manager, organization_name='Rival')
        event_b = Event.objects.create(
            organizer=rival_manager,
            title='Secret Showcase Event B',
            category='Nightlife',
            date=timezone.now().date() + timedelta(days=15),
            start_time=time(21, 0),
            venue_name='Underground Club',
            city='Mohali',
            status='published'
        )
        tier_b = TicketTier.objects.create(event=event_b, name='GA', price=Decimal('20.00'), capacity=50)

        order_a = Order.objects.create(
            user=self.attendee, event=self.event, tier=self.tier,
            quantity=1, unit_price=self.tier.price, total_amount=self.tier.price, status='Confirmed'
        )
        ticket_a = AttendeeTicket.objects.create(
            order=order_a, event=self.event, tier=self.tier,
            attendee_name='Guest Alpha', attendee_email='alpha@test.com'
        )

        order_b = Order.objects.create(
            user=self.attendee, event=event_b, tier=tier_b,
            quantity=1, unit_price=tier_b.price, total_amount=tier_b.price, status='Confirmed'
        )
        ticket_b = AttendeeTicket.objects.create(
            order=order_b, event=event_b, tier=tier_b,
            attendee_name='Guest Beta', attendee_email='beta@test.com'
        )

        # Create a staff user (Account role: MANAGER with OrganizerProfile)
        staff_user = User.objects.create_user(
            email='gatekeeper@evento.com',
            password='Password123!',
            full_name='Gate Keeper',
            role=MANAGER
        )
        OrganizerProfile.objects.create(user=staff_user, organization_name='Gate Operations')

        # 1. Assign staff to Event A with can_view_attendees=True, can_check_in=True, can_edit_attendees=False
        staff_assignment = EventStaff.objects.create(
            event=self.event,
            user=staff_user,
            can_view_attendees=True,
            can_check_in=True,
            can_edit_attendees=False
        )

        # Login as staff_user
        login_res = self.client.post('/api/auth/login/', {
            'email': 'gatekeeper@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 2. Staff Manager can view attendees of assigned Event A via Manager Attendees endpoint
        mgr_view_res = self.client.get(f'/api/tickets/manager/attendees/?event={self.event.id}')
        self.assertEqual(mgr_view_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mgr_view_res.data['attendees']), 1)
        self.assertEqual(mgr_view_res.data['attendees'][0]['attendeeName'], 'Guest Alpha')

        # Also verify event appears in events list
        events_in_dropdown = [e['id'] for e in mgr_view_res.data['events']]
        self.assertIn(self.event.id, events_in_dropdown)

        # 3. Staff can check in ticket on Event A via Manager Gate Check-in endpoint
        checkin_res = self.client.patch(
            f'/api/tickets/manager/attendees/{ticket_a.ticket_code}/check-in/'
        )
        self.assertEqual(checkin_res.status_code, status.HTTP_200_OK)
        self.assertTrue(checkin_res.data['checkedIn'])

        ticket_a.refresh_from_db()
        self.assertTrue(ticket_a.is_checked_in)

        # 4. STRICT EVENT ISOLATION: Staff of Event A attempts to check in ticket on Event B (not staff)
        iso_checkin_res = self.client.patch(
            f'/api/tickets/manager/attendees/{ticket_b.ticket_code}/check-in/'
        )
        self.assertEqual(iso_checkin_res.status_code, status.HTTP_403_FORBIDDEN)

        # 5. FINANCIAL ISOLATION: Staff member has zero sales transactions for another manager's event
        sales_res = self.client.get('/api/tickets/manager/sales/')
        self.assertEqual(sales_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(sales_res.data['transactions']), 0)

    def test_paypal_sandbox_workflow(self):
        from unittest.mock import patch
        from events.models import Seat

        # Create seats for event
        seat1 = Seat.objects.create(
            event=self.event,
            tier=self.tier,
            section_name='Main Hall',
            row='A',
            seat_number='1',
            status='available'
        )
        seat2 = Seat.objects.create(
            event=self.event,
            tier=self.tier,
            section_name='Main Hall',
            row='A',
            seat_number='2',
            status='available'
        )

        # Login as attendee
        login_res = self.client.post('/api/auth/login/', {
            'email': 'attendee@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Config endpoint
        config_res = self.client.get('/api/tickets/paypal/config/')
        self.assertEqual(config_res.status_code, status.HTTP_200_OK)
        self.assertIn('clientId', config_res.data)
        self.assertEqual(config_res.data['mode'], 'sandbox')

        # 2. Create PayPal Order (Phase 1: Reserve seats for 10 min)
        with patch('tickets.views.create_paypal_order') as mock_create:
            mock_create.return_value = {'id': 'PAYPAL-TEST-ORDER-123'}
            create_res = self.client.post('/api/tickets/paypal/create-order/', {
                'eventId': self.event.id,
                'seatIds': [seat1.id, seat2.id],
                'attendeeName': 'Event Attendee'
            }, format='json')

            self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
            self.assertEqual(create_res.data['paypalOrderId'], 'PAYPAL-TEST-ORDER-123')
            order_id = create_res.data['orderId']

            # Check that seats are now temporarily reserved
            seat1.refresh_from_db()
            seat2.refresh_from_db()
            self.assertEqual(seat1.status, 'reserved')
            self.assertEqual(seat2.status, 'reserved')
            self.assertIsNotNone(seat1.reserved_until)

        # 3. Double-reservation protection (Second user tries to reserve same seats)
        other_user = User.objects.create_user(
            email='other@evento.com',
            password='Password123!',
            full_name='Other User',
            role=USER
        )
        other_login = self.client.post('/api/auth/login/', {
            'email': 'other@evento.com',
            'password': 'Password123!'
        })
        other_token = other_login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {other_token}')

        conflict_res = self.client.post('/api/tickets/paypal/create-order/', {
            'eventId': self.event.id,
            'seatIds': [seat1.id],
            'attendeeName': 'Other User'
        }, format='json')
        self.assertEqual(conflict_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('currently held', conflict_res.data['detail'])

        # 4. Cancel workflow (User cancels PayPal modal, releases holds)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        cancel_res = self.client.post('/api/tickets/paypal/cancel-order/', {
            'orderId': order_id
        }, format='json')
        self.assertEqual(cancel_res.status_code, status.HTTP_200_OK)

        seat1.refresh_from_db()
        seat2.refresh_from_db()
        self.assertEqual(seat1.status, 'available')
        self.assertEqual(seat2.status, 'available')

        # 5. Full Success Flow: Create -> Capture -> Booked & Issued
        with patch('tickets.views.create_paypal_order') as mock_create, \
             patch('tickets.views.capture_paypal_order') as mock_capture:
            
            mock_create.return_value = {'id': 'PAYPAL-COMPLETED-456'}
            mock_capture.return_value = {
                'id': 'PAYPAL-COMPLETED-456',
                'status': 'COMPLETED',
                'purchase_units': [{'payments': {'captures': [{'id': 'CAPTURE-789'}]}}]
            }

            create_res2 = self.client.post('/api/tickets/paypal/create-order/', {
                'eventId': self.event.id,
                'seatIds': [seat1.id, seat2.id],
                'attendeeName': 'Event Attendee'
            }, format='json')
            self.assertEqual(create_res2.status_code, status.HTTP_201_CREATED)
            order2_id = create_res2.data['orderId']

            capture_res = self.client.post('/api/tickets/paypal/capture-order/', {
                'orderId': order2_id,
                'paypalOrderId': 'PAYPAL-COMPLETED-456'
            }, format='json')
            self.assertEqual(capture_res.status_code, status.HTTP_200_OK)
            self.assertEqual(capture_res.data['status'], 'Confirmed')

            seat1.refresh_from_db()
            seat2.refresh_from_db()
            self.assertEqual(seat1.status, 'booked')
            self.assertEqual(seat2.status, 'booked')
            self.assertIsNotNone(seat1.ticket)
            self.assertIsNotNone(seat2.ticket)

    def test_fee_calculation_when_passed_to_buyer(self):
        # Event with pass_platform_fee_to_buyer=True
        self.event.pass_platform_fee_to_buyer = True
        self.event.save()

        login_res = self.client.post('/api/auth/login/', {
            'email': 'attendee@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 2 tickets @ $35.00 = $70.00 subtotal. 3.5% fee = $2.45. Grand total = $72.45
        checkout_res = self.client.post('/api/tickets/checkout/', {
            'eventId': self.event.id,
            'tierId': self.tier.id,
            'quantity': 2,
            'paymentMethod': 'PayPal (Sandbox)',
            'attendeeName': 'Event Attendee'
        }, format='json')
        self.assertEqual(checkout_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(checkout_res.data['fees'], '$2.45')
        self.assertEqual(checkout_res.data['total'], '$72.45')

        # Check organizer available payout balance -> Should be exactly $70.00 (no double cut)
        from payouts.views import calculate_organizer_financials
        fin = calculate_organizer_financials(self.manager)
        self.assertEqual(fin['gross_ticket_sales'], Decimal('70.00'))
        self.assertEqual(fin['organizer_net_earnings'], Decimal('70.00'))
        self.assertEqual(fin['available_balance'], Decimal('70.00'))

    def test_fee_calculation_when_absorbed_by_organizer(self):
        # Event with pass_platform_fee_to_buyer=False
        self.event.pass_platform_fee_to_buyer = False
        self.event.save()

        login_res = self.client.post('/api/auth/login/', {
            'email': 'attendee@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 2 tickets @ $35.00 = $70.00 subtotal. Fee to buyer = $0.00. Grand total = $70.00
        checkout_res = self.client.post('/api/tickets/checkout/', {
            'eventId': self.event.id,
            'tierId': self.tier.id,
            'quantity': 2,
            'paymentMethod': 'PayPal (Sandbox)',
            'attendeeName': 'Event Attendee'
        }, format='json')
        self.assertEqual(checkout_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(checkout_res.data['fees'], '$0.00')
        self.assertEqual(checkout_res.data['total'], '$70.00')

        # Check organizer available payout balance -> $70.00 - 3.5% ($2.45) = $67.55
        from payouts.views import calculate_organizer_financials
        fin = calculate_organizer_financials(self.manager)
        self.assertEqual(fin['gross_ticket_sales'], Decimal('70.00'))
        self.assertEqual(fin['total_platform_fees'], Decimal('2.45'))
        self.assertEqual(fin['organizer_net_earnings'], Decimal('67.55'))
        self.assertEqual(fin['available_balance'], Decimal('67.55'))


