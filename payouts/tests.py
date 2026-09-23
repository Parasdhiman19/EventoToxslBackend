from datetime import date, time
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, OrganizerProfile, SettlementAccount
from accounts.constants import USER, MANAGER
from events.models import Event, TicketTier
from tickets.models import Order, AttendeeTicket
from payouts.models import Payout


class PayoutsTests(TestCase):
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
        self.settlement_acc = SettlementAccount.objects.create(
            organizer=self.manager,
            method_type='paypal',
            paypal_email='primary.host@evento.com',
            is_primary=True,
            status='Primary'
        )
        self.attendee = User.objects.create_user(
            email='attendee@evento.com',
            password='Password123!',
            full_name='Event Attendee',
            role=USER
        )
        self.event = Event.objects.create(
            organizer=self.manager,
            title='Electronic Solstice 2026',
            category='Music & Concerts',
            date=date(2026, 8, 28),
            start_time=time(20, 0),
            venue_name='Warehouse Stage',
            city='Chandigarh',
            status='published'
        )
        self.tier = TicketTier.objects.create(
            event=self.event,
            name='General Admission',
            price=Decimal('100.00'),
            capacity=100,
            sold_count=5
        )
        self.order = Order.objects.create(
            user=self.attendee,
            event=self.event,
            tier=self.tier,
            quantity=5,
            unit_price=Decimal('100.00'),
            fees=Decimal('17.50'),
            total_amount=Decimal('517.50'),
            status='Confirmed'
        )

        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!'
        })
        self.token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

    def test_manager_overview_and_payouts(self):
        # Test manager overview
        overview_res = self.client.get('/api/payouts/manager/overview/')
        self.assertEqual(overview_res.status_code, status.HTTP_200_OK)
        self.assertIn('stats', overview_res.data)
        self.assertIn('activeEvents', overview_res.data)
        self.assertIn('recentTransactions', overview_res.data)

        # Test manager payouts dashboard
        payouts_res = self.client.get('/api/payouts/manager/payouts/')
        self.assertEqual(payouts_res.status_code, status.HTTP_200_OK)
        self.assertIn('balanceCards', payouts_res.data)
        self.assertIn('payoutMethods', payouts_res.data)
        self.assertTrue(payouts_res.data['hasPayoutMethod'])

    def test_add_paypal_payout_method(self):
        # Add PayPal account
        res = self.client.post('/api/payouts/manager/methods/', {
            'paypalEmail': 'payouts.host@evento.com',
            'isPrimary': True
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['methodType'], 'paypal')
        self.assertEqual(res.data['paypalEmail'], 'payouts.host@evento.com')
        self.assertTrue(res.data['isPrimary'])

        # Verify old account is no longer primary
        self.settlement_acc.refresh_from_db()
        self.assertFalse(self.settlement_acc.is_primary)

    def test_delete_and_set_primary_payout_method(self):
        # Create second account
        new_acc = SettlementAccount.objects.create(
            organizer=self.manager,
            method_type='paypal',
            paypal_email='second@evento.com'
        )

        # Set new_acc as primary via PATCH
        patch_res = self.client.patch(f'/api/payouts/manager/methods/{new_acc.id}/', {
            'isPrimary': True
        })
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        new_acc.refresh_from_db()
        self.assertTrue(new_acc.is_primary)

        # Delete new_acc
        del_res = self.client.delete(f'/api/payouts/manager/methods/{new_acc.id}/')
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)
        self.assertFalse(SettlementAccount.objects.filter(pk=new_acc.id).exists())


    def test_request_payout_without_methods_fails(self):
        # Remove all methods
        SettlementAccount.objects.filter(organizer=self.manager).delete()

        res = self.client.post('/api/payouts/manager/payouts/request/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Please connect a PayPal account', res.data['detail'])


    def test_request_payout_exceeding_balance_fails(self):
        res = self.client.post('/api/payouts/manager/payouts/request/', {
            'amount': '99999.00'
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceeds available balance', res.data['detail'])

    def test_request_payout_below_minimum_fails(self):
        res = self.client.post('/api/payouts/manager/payouts/request/', {
            'amount': '5.00'
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Minimum withdrawal amount is $10.00', res.data['detail'])

    def test_request_paypal_payout_success(self):
        paypal_acc = SettlementAccount.objects.create(
            organizer=self.manager,
            method_type='paypal',
            paypal_email='organizer.paypal@example.com',
            is_primary=True
        )

        res = self.client.post('/api/payouts/manager/payouts/request/', {
            'amount': '150.00',
            'methodId': paypal_acc.id
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('payout', res.data)
        self.assertEqual(res.data['payout']['methodType'], 'paypal')
        self.assertIn('PayPal (organizer.paypal@example.com)', res.data['payout']['method'])

        # Verify Payout recorded in DB
        payout = Payout.objects.filter(organizer=self.manager).first()
        self.assertIsNotNone(payout)
        self.assertEqual(payout.net_disbursed, Decimal('150.00'))
        self.assertEqual(payout.method_type, 'paypal')

