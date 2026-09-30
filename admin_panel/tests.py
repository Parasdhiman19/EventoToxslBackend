from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, OrganizerProfile
from events.models import Event, TicketTier
from tickets.models import Order
from admin_panel.models import HomepageBanner, RecommendedEvent, PlatformSetting, AuditLog


class AdminPanelTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Normal Customer
        self.customer = User.objects.create_user(
            email='customer@example.com',
            password='Password123!',
            full_name='Regular User',
            role='user'
        )

        # Super Admin
        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='Password123!',
            full_name='Platform Admin',
            role='admin',
            is_staff=True,
            is_superuser=True
        )

        # Organizer
        self.organizer = User.objects.create_user(
            email='organizer@example.com',
            password='Password123!',
            full_name='Stage Host',
            role='manager'
        )
        self.org_profile = OrganizerProfile.objects.create(
            user=self.organizer,
            organization_name='Starlight Stages'
        )

        # Event
        self.event = Event.objects.create(
            organizer=self.organizer,
            title='Cosmic Music Night',
            category='Music',
            date=timezone.now().date() + timedelta(days=10),
            start_time=timezone.now().time(),
            venue_name='Arena 1',
            city='Chandigarh',
            status='published'
        )
        self.tier = TicketTier.objects.create(
            event=self.event,
            name='VIP',
            price=100.00,
            capacity=50
        )

    def test_admin_dashboard_stats_requires_admin(self):
        # Unauthenticated fails
        res = self.client.get('/api/admin/dashboard/stats/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Customer forbidden
        self.client.force_authenticate(user=self.customer)
        res = self.client.get('/api/admin/dashboard/stats/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin authorized
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/admin/dashboard/stats/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('financials', res.data)
        self.assertIn('operations', res.data)

    def test_banner_crud_and_reorder(self):
        self.client.force_authenticate(user=self.admin)

        # Create Banner
        res = self.client.post('/api/admin/banners/', {
            'title': 'Grand Symphony 2026',
            'subtitle': 'An orchestral evening',
            'imageUrl': 'https://example.com/banner.jpg',
            'eventId': self.event.id,
            'ctaText': 'Book Now',
            'displayOrder': 1,
            'isActive': True
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        banner_id = res.data['id']

        # List Banners
        res = self.client.get('/api/admin/banners/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 1)

        # Update Banner
        res = self.client.patch(f'/api/admin/banners/{banner_id}/', {
            'title': 'Grand Symphony 2026 - Updated'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['title'], 'Grand Symphony 2026 - Updated')

        # Reorder Banners
        res = self.client.post('/api/admin/banners/reorder/', {
            'order': [{'id': banner_id, 'displayOrder': 5}]
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Delete Banner
        res = self.client.delete(f'/api/admin/banners/{banner_id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_recommended_events_flow(self):
        self.client.force_authenticate(user=self.admin)

        # Add Recommended Event
        res = self.client.post('/api/admin/recommended-events/', {
            'eventId': self.event.id,
            'priorityRank': 1,
            'isActive': True
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        entry_id = res.data['id']

        # Public Content Endpoint
        self.client.logout()
        res = self.client.get('/api/admin/content/homepage/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('recommendations', res.data)
        self.assertIn('banners', res.data)

    def test_user_suspension_flow(self):
        self.client.force_authenticate(user=self.admin)

        # Suspend User
        res = self.client.post(f'/api/admin/users/{self.customer.id}/suspend/', {
            'reason': 'Terms violation'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_suspended)

        # Unsuspend User
        res = self.client.post(f'/api/admin/users/{self.customer.id}/unsuspend/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_suspended)

    def test_event_status_override(self):
        self.client.force_authenticate(user=self.admin)

        res = self.client.patch(f'/api/admin/events/{self.event.id}/status/', {
            'status': 'suspended',
            'reason': 'Flagged by moderation'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, 'suspended')
