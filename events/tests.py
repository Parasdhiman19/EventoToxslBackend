from datetime import date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, OrganizerProfile
from accounts.constants import USER, MANAGER
from events.models import Event, TicketTier, SavedEvent


class EventsTests(TestCase):
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

        self.manager_two = User.objects.create_user(
            email='rival@evento.com',
            password='Password123!',
            full_name='Rival Organizer',
            role=MANAGER
        )
        self.org_profile_two = OrganizerProfile.objects.create(
            user=self.manager_two,
            organization_name='Rival Events',
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
            description='An immersive music showcase.',
            date=future_date,
            start_time=time(20, 0),
            end_time=time(23, 0),
            venue_name='Warehouse Stage',
            city='Chandigarh',
            status='published',
            is_featured=True
        )
        self.tier1 = TicketTier.objects.create(
            event=self.event,
            name='General Admission',
            price=Decimal('35.00'),
            capacity=100,
            sold_count=10
        )
        self.tier2 = TicketTier.objects.create(
            event=self.event,
            name='VIP Pass',
            price=Decimal('75.00'),
            capacity=20,
            sold_count=0
        )

    def test_public_event_list(self):
        res = self.client.get('/api/events/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['title'], 'Electronic Solstice 2026')
        self.assertEqual(res.data[0]['startingPrice'], '$35.00')

    def test_public_event_list_pagination(self):
        res = self.client.get('/api/events/?page=1&page_size=5')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('results', res.data)
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['totalPages'], 1)
        self.assertEqual(res.data['currentPage'], 1)
        self.assertFalse(res.data['hasMore'])
        self.assertEqual(len(res.data['results']), 1)
        self.assertEqual(res.data['results'][0]['title'], 'Electronic Solstice 2026')

    def test_featured_event(self):
        res = self.client.get('/api/events/featured/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['title'], 'Electronic Solstice 2026')

    def test_event_detail(self):
        res = self.client.get(f'/api/events/{self.event.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data['tiers']), 2)

    def test_manager_event_create_and_manage(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Create event with camelCase keys
        create_res = self.client.post('/api/events/manager/', {
            'title': 'Design & Art Summit',
            'category': 'Art & Exhibitions',
            'description': 'A summit showcasing modern visual designs.',
            'date': '2026-09-15',
            'startTime': '10:00',
            'endTime': '18:00',
            'venueName': 'Gallery Hall',
            'city': 'Delhi NCR',
            'status': 'published',
            'tiers': [
                {'name': 'Standard Entry', 'price': 25.00, 'capacity': 50, 'description': 'Main gallery pass'},
                {'name': 'VIP All Access', 'price': 60.00, 'capacity': 10, 'description': 'Exclusive lounge'}
            ]
        }, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        new_event_id = create_res.data['id']
        self.assertEqual(create_res.data['venueName'], 'Gallery Hall')
        self.assertEqual(create_res.data['startTime'], '10:00')
        self.assertEqual(create_res.data['endTime'], '18:00')
        self.assertEqual(len(create_res.data['tiers']), 2)

        # List manager events
        list_res = self.client.get('/api/events/manager/')
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 2)

        # Patch event title and date
        patch_res = self.client.patch(f'/api/events/manager/{new_event_id}/', {
            'title': 'Design & Art Summit 2026 (Updated)'
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['title'], 'Design & Art Summit 2026 (Updated)')

    def test_tier_reconciliation_and_capacity_enforcement(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Tier 1 has sold_count = 10. Attempting to reduce capacity to 5 should fail (400)
        invalid_patch = self.client.patch(f'/api/events/manager/{self.event.id}/', {
            'tiers': [
                {'id': self.tier1.id, 'name': 'General Admission', 'price': 35.00, 'capacity': 5},
                {'id': self.tier2.id, 'name': 'VIP Pass', 'price': 75.00, 'capacity': 20}
            ]
        }, format='json')
        self.assertEqual(invalid_patch.status_code, status.HTTP_400_BAD_REQUEST)

        # Attempting to delete tier1 (which has 10 sold tickets) should fail (400)
        delete_sold_tier = self.client.patch(f'/api/events/manager/{self.event.id}/', {
            'tiers': [
                {'id': self.tier2.id, 'name': 'VIP Pass', 'price': 75.00, 'capacity': 20}
            ]
        }, format='json')
        self.assertEqual(delete_sold_tier.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid update: update tier1, delete unused tier2, add new tier3
        valid_patch = self.client.patch(f'/api/events/manager/{self.event.id}/', {
            'tiers': [
                {'id': self.tier1.id, 'name': 'GA Early Bird', 'price': 40.00, 'capacity': 120},
                {'name': 'Backstage Pass', 'price': 150.00, 'capacity': 15, 'description': 'Backstage pass'}
            ]
        }, format='json')
        self.assertEqual(valid_patch.status_code, status.HTTP_200_OK)
        updated_tiers = valid_patch.data['tiers']
        self.assertEqual(len(updated_tiers), 2)
        # Tier 1 preserved ID and sold_count
        self.assertEqual(updated_tiers[0]['id'], self.tier1.id)
        self.assertEqual(updated_tiers[0]['soldCount'], 10)
        self.assertEqual(updated_tiers[0]['name'], 'GA Early Bird')
        # Tier 2 was safely deleted
        self.assertFalse(TicketTier.objects.filter(id=self.tier2.id).exists())

    def test_end_time_validation(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # End time before start time
        res = self.client.post('/api/events/manager/', {
            'title': 'Midnight Show',
            'category': 'Nightlife',
            'description': 'A late night event in downtown.',
            'date': '2026-10-10',
            'startTime': '22:00',
            'endTime': '20:00',
            'venueName': 'Baseway Club',
            'city': 'Mohali'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_archive_event(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        del_res = self.client.delete(f'/api/events/manager/{self.event.id}/')
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, 'past')

    def test_manager_permanent_delete_event(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Create temporary event to permanently delete
        from events.models import Event
        temp_event = Event.objects.create(
            organizer=self.manager,
            title="Temporary Test Stage",
            category="Music & Concerts",
            description="A stage created to test permanent deletion.",
            date="2026-12-31",
            start_time="20:00:00",
            venue_name="Temp Arena",
            city="Chandigarh",
            status="draft"
        )
        del_res = self.client.delete(f'/api/events/manager/{temp_event.id}/?permanent=true')
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)
        self.assertTrue(del_res.data.get('deleted'))
        self.assertFalse(Event.objects.filter(pk=temp_event.id).exists())

    def test_manager_permanent_delete_blocked_with_ticket_sales(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # self.event has self.tier1 with sold_count=10
        del_res = self.client.delete(f'/api/events/manager/{self.event.id}/?permanent=true')
        self.assertEqual(del_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(del_res.data.get('can_delete'))
        self.assertTrue(del_res.data.get('has_sales'))
        # Ensure event was not deleted
        self.assertTrue(Event.objects.filter(pk=self.event.id).exists())

    def test_cross_manager_isolation(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'rival@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Rival manager cannot get or edit manager 1's event
        get_res = self.client.get(f'/api/events/manager/{self.event.id}/')
        self.assertEqual(get_res.status_code, status.HTTP_404_NOT_FOUND)

        patch_res = self.client.patch(f'/api/events/manager/{self.event.id}/', {
            'title': 'Hacked Title'
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthorized_access(self):
        # Regular attendee user cannot access manager endpoints
        login_res = self.client.post('/api/auth/login/', {
            'email': 'attendee@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = self.client.get('/api/events/manager/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_bookmark_toggle_and_saved_events(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'attendee@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Toggle bookmark ON
        toggle_res = self.client.post(f'/api/events/saved/{self.event.id}/toggle/')
        self.assertEqual(toggle_res.status_code, status.HTTP_200_OK)
        self.assertTrue(toggle_res.data['isBookmarked'])

        # Get saved events
        saved_res = self.client.get('/api/events/saved/')
        self.assertEqual(saved_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(saved_res.data), 1)

        # Toggle bookmark OFF
        toggle_off = self.client.post(f'/api/events/saved/{self.event.id}/toggle/')
        self.assertFalse(toggle_off.data['isBookmarked'])

    def test_cannot_create_event_with_duplicate_title(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!',
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        payload = {
            'title': 'Electronic Solstice 2026',  # duplicate title
            'category': 'Tech & Conferences',
            'description': 'Duplicate event title test.',
            'date': '2026-09-15',
            'startTime': '10:00:00',
            'endTime': '17:00:00',
            'venueName': 'Tech Hall',
            'city': 'Chandigarh',
            'status': 'published',
            'tiers': [
                {'name': 'Pass', 'price': 50.0, 'capacity': 100}
            ]
        }
        res = self.client.post('/api/events/manager/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', res.data)

    def test_can_update_event_retaining_own_title(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!',
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Updating the event with its own existing title should succeed
        res = self.client.patch(f'/api/events/manager/{self.event.id}/', {
            'title': 'Electronic Solstice 2026',
            'description': 'Updated description keeping same title.'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_expired_event_computed_as_past(self):
        past_event = Event.objects.create(
            organizer=self.manager,
            title='Retro Showcase 2020',
            category='Music & Concerts',
            description='A past event from yesterday.',
            date=timezone.now().date() - timedelta(days=2),
            start_time=time(18, 0),
            end_time=time(21, 0),
            venue_name='Old Hall',
            city='Chandigarh',
            status='published',
        )
        self.assertTrue(past_event.is_ended)
        self.assertEqual(past_event.computed_status, 'past')

        # Serializer should report status as 'past' and isEnded as True
        res = self.client.get(f'/api/events/{past_event.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'past')
        self.assertTrue(res.data['isEnded'])

    def test_public_event_list_excludes_ended_events(self):
        # Create an expired event
        Event.objects.create(
            organizer=self.manager,
            title='Expired Retrospective Expo',
            category='Music & Concerts',
            description='Expired event.',
            date=timezone.now().date() - timedelta(days=5),
            start_time=time(18, 0),
            end_time=time(21, 0),
            venue_name='Old Hall',
            city='Chandigarh',
            status='published',
        )
        # Public discovery should only return the active event
        res = self.client.get('/api/events/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        titles = [e['title'] for e in res.data]
        self.assertIn('Electronic Solstice 2026', titles)
        self.assertNotIn('Expired Retrospective Expo', titles)

    def test_manager_status_tabs_filter_ended_events(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!',
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Create expired event
        Event.objects.create(
            organizer=self.manager,
            title='Old Manager Conference',
            category='Tech & Conferences',
            description='Expired event.',
            date=timezone.now().date() - timedelta(days=3),
            start_time=time(10, 0),
            end_time=time(17, 0),
            venue_name='Convention Center',
            city='Chandigarh',
            status='published',
        )

        # Published tab should only have the upcoming event
        pub_res = self.client.get('/api/events/manager/?status=published')
        self.assertEqual(pub_res.status_code, status.HTTP_200_OK)
        pub_titles = [e['title'] for e in pub_res.data]
        self.assertIn('Electronic Solstice 2026', pub_titles)
        self.assertNotIn('Old Manager Conference', pub_titles)

        # Past tab should include the expired event
        past_res = self.client.get('/api/events/manager/?status=past')
        self.assertEqual(past_res.status_code, status.HTTP_200_OK)
        past_titles = [e['title'] for e in past_res.data]
        self.assertIn('Old Manager Conference', past_titles)

    def test_cannot_checkout_for_ended_event(self):
        past_event = Event.objects.create(
            organizer=self.manager,
            title='Concluded Concert',
            category='Music & Concerts',
            description='Concluded concert description.',
            date=timezone.now().date() - timedelta(days=1),
            start_time=time(19, 0),
            end_time=time(22, 0),
            venue_name='Old Stadium',
            city='Chandigarh',
            status='published',
        )
        tier = TicketTier.objects.create(
            event=past_event,
            name='General',
            price=Decimal('25.00'),
            capacity=50,
            sold_count=0
        )

        # Login as attendee
        login_res = self.client.post('/api/auth/login/', {
            'email': 'attendee@evento.com',
            'password': 'Password123!',
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        checkout_payload = {
            'eventId': past_event.id,
            'tierId': tier.id,
            'quantity': 1,
            'paymentMethod': 'UPI • Axis Bank',
        }
        res = self.client.post('/api/tickets/checkout/', checkout_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('eventId', res.data)

    def test_manager_staff_search_assign_update_delete(self):
        # Login as manager
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!',
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Search for regular attendee -> Should return empty (non-managers cannot be staff)
        search_attendee_res = self.client.get('/api/events/manager/staff/users/search/?q=attendee')
        self.assertEqual(search_attendee_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(search_attendee_res.data), 0)

        # 2. Attempt to assign regular attendee as staff -> Rejected (400 Bad Request)
        invalid_assign_res = self.client.post(f'/api/events/manager/{self.event.id}/staff/', {
            'userId': self.attendee.id,
            'canViewAttendees': True,
            'canCheckIn': True,
        }, format='json')
        self.assertEqual(invalid_assign_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('manager', str(invalid_assign_res.data).lower())

        # 3. Search for registered manager (manager_two) -> Found
        search_mgr_res = self.client.get('/api/events/manager/staff/users/search/?q=rival')
        self.assertEqual(search_mgr_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(search_mgr_res.data), 1)
        self.assertEqual(search_mgr_res.data[0]['email'], 'rival@evento.com')

        # 4. Assign manager_two as staff -> Success
        assign_res = self.client.post(f'/api/events/manager/{self.event.id}/staff/', {
            'userId': self.manager_two.id,
            'canViewAttendees': True,
            'canCheckIn': True,
            'canEditAttendees': False
        }, format='json')
        self.assertEqual(assign_res.status_code, status.HTTP_201_CREATED)
        staff_id = assign_res.data['id']
        self.assertTrue(assign_res.data['canViewAttendees'])
        self.assertTrue(assign_res.data['canCheckIn'])
        self.assertFalse(assign_res.data['canEditAttendees'])

        # 5. Duplicate assignment rejected
        dup_res = self.client.post(f'/api/events/manager/{self.event.id}/staff/', {
            'userId': self.manager_two.id
        }, format='json')
        self.assertEqual(dup_res.status_code, status.HTTP_400_BAD_REQUEST)

        # 6. List staff
        list_res = self.client.get(f'/api/events/manager/{self.event.id}/staff/')
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)

        # 7. Update permissions
        patch_res = self.client.patch(f'/api/events/manager/{self.event.id}/staff/{staff_id}/', {
            'canEditAttendees': True
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertTrue(patch_res.data['canEditAttendees'])

        # 8. Delete staff
        del_res = self.client.delete(f'/api/events/manager/{self.event.id}/staff/{staff_id}/')
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)

        # Confirm deleted
        list_after = self.client.get(f'/api/events/manager/{self.event.id}/staff/')
        self.assertEqual(len(list_after.data), 0)

    def test_staff_assigned_events_list(self):
        from events.models import EventStaff
        EventStaff.objects.create(
            event=self.event,
            user=self.manager_two,
            can_view_attendees=True,
            can_check_in=True
        )

        # Login as manager_two
        login_res = self.client.post('/api/auth/login/', {
            'email': 'rival@evento.com',
            'password': 'Password123!',
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        staff_events_res = self.client.get('/api/events/staff/')
        self.assertEqual(staff_events_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(staff_events_res.data), 1)
        self.assertEqual(staff_events_res.data[0]['id'], self.event.id)
        self.assertTrue(staff_events_res.data[0]['permissions']['can_view_attendees'])

        # Also check Manager events list with status=staff
        mgr_staff_res = self.client.get('/api/events/manager/?status=staff')
        self.assertEqual(mgr_staff_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mgr_staff_res.data), 1)
        self.assertEqual(mgr_staff_res.data[0]['id'], self.event.id)

    def test_manager_seating_studio_and_seat_checkout_flow(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'organizer@evento.com',
            'password': 'Password123!',
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Save seating layout via Manager Seating API
        layout_payload = {
            'seatingLayout': {
                'dimensions': {'rows': 3, 'columns': 4},
                'stagePosition': 'top',
                'aisles': [2],
                'tiers': [
                    {'name': 'VIP Pass', 'price': 80.00, 'color': '#f59e0b', 'description': 'Front row prime view'},
                    {'name': 'General Admission', 'price': 40.00, 'color': '#10b981', 'description': 'Standard seating'}
                ],
                'grid': [
                    # Row A (VIP)
                    {'row': 'A', 'col': '1', 'seatNumber': '1', 'sectionName': 'Main Hall', 'tierName': 'VIP Pass', 'status': 'available', 'isAccessible': False},
                    {'row': 'A', 'col': '2', 'seatNumber': '2', 'sectionName': 'Main Hall', 'tierName': 'VIP Pass', 'status': 'available', 'isAccessible': False},
                    {'row': 'A', 'col': '3', 'seatNumber': '3', 'sectionName': 'Main Hall', 'tierName': 'VIP Pass', 'status': 'available', 'isAccessible': False},
                    {'row': 'A', 'col': '4', 'seatNumber': '4', 'sectionName': 'Main Hall', 'tierName': 'VIP Pass', 'status': 'available', 'isAccessible': False},
                    # Row B (GA)
                    {'row': 'B', 'col': '1', 'seatNumber': '1', 'sectionName': 'Main Hall', 'tierName': 'General Admission', 'status': 'available', 'isAccessible': False},
                    {'row': 'B', 'col': '2', 'seatNumber': '2', 'sectionName': 'Main Hall', 'tierName': 'General Admission', 'status': 'available', 'isAccessible': True},
                    {'row': 'B', 'col': '3', 'seatNumber': '3', 'sectionName': 'Main Hall', 'tierName': 'General Admission', 'status': 'available', 'isAccessible': False},
                    {'row': 'B', 'col': '4', 'seatNumber': '4', 'sectionName': 'Main Hall', 'tierName': 'General Admission', 'status': 'available', 'isAccessible': False},
                ]
            }
        }

        seating_res = self.client.post(f'/api/events/manager/{self.event.id}/seating/', layout_payload, format='json')
        self.assertEqual(seating_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(seating_res.data['seats']), 8)
        self.assertEqual(len(seating_res.data['tiers']), 2)

        # 2. Check public seating endpoint
        public_seat_res = self.client.get(f'/api/events/{self.event.id}/seating/')
        self.assertEqual(public_seat_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(public_seat_res.data['seats']), 8)

        # 3. Attendee selects specific seats and checks out
        self.client.credentials()  # Clear manager credentials
        attendee_login = self.client.post('/api/auth/login/', {
            'email': 'attendee@evento.com',
            'password': 'Password123!',
        })
        attendee_token = attendee_login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {attendee_token}')

        vip_seat_1 = public_seat_res.data['seats'][0]  # Row A Seat 1
        vip_seat_2 = public_seat_res.data['seats'][1]  # Row A Seat 2

        checkout_res = self.client.post('/api/tickets/checkout/', {
            'eventId': self.event.id,
            'seatIds': [vip_seat_1['id'], vip_seat_2['id']],
            'paymentMethod': 'Credit Card',
            'attendeeName': 'VIP Attendee',
            'attendeeEmail': 'attendee@evento.com'
        }, format='json')
        self.assertEqual(checkout_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(checkout_res.data['quantity'], 2)

        # 4. Verify seats are now marked booked and cannot be double booked
        dup_checkout = self.client.post('/api/tickets/checkout/', {
            'eventId': self.event.id,
            'seatIds': [vip_seat_1['id']],
            'paymentMethod': 'Credit Card',
            'attendeeName': 'Another Attendee',
            'attendeeEmail': 'another@evento.com'
        }, format='json')
        self.assertEqual(dup_checkout.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('seatIds', dup_checkout.data)


class SocialInteractionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organizer = User.objects.create_user(
            email='organizer_social@evento.com',
            password='Password123!',
            full_name='Master Host',
            role=MANAGER
        )
        self.user1 = User.objects.create_user(
            email='alice@evento.com',
            password='Password123!',
            full_name='Alice Smith',
            role=USER
        )
        self.user2 = User.objects.create_user(
            email='bob@evento.com',
            password='Password123!',
            full_name='Bob Jones',
            role=USER
        )
        self.user3 = User.objects.create_user(
            email='charlie@evento.com',
            password='Password123!',
            full_name='Charlie Brown',
            role=USER
        )

        future_date = timezone.now().date() + timedelta(days=20)
        self.event1 = Event.objects.create(
            organizer=self.organizer,
            title='Sunset Rooftop Beats',
            category='Music & Concerts',
            description='Live electronic sunset session.',
            date=future_date,
            start_time=time(18, 0),
            end_time=time(22, 0),
            venue_name='Sky Bar Lounge',
            city='Chandigarh',
            status='published'
        )
        self.event2 = Event.objects.create(
            organizer=self.organizer,
            title='Tech Horizons Summit',
            category='Tech & Conferences',
            description='Annual developer conference.',
            date=future_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
            venue_name='Convention Center',
            city='Chandigarh',
            status='published'
        )

    def test_like_and_unlike_event(self):
        # Unauthenticated like attempt should fail
        res = self.client.post(f'/api/events/{self.event1.id}/like/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate Alice
        self.client.force_authenticate(user=self.user1)

        # Alice likes event1
        res = self.client.post(f'/api/events/{self.event1.id}/like/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['isLiked'])
        self.assertEqual(res.data['likesCount'], 1)

        # Verify like status via GET
        get_res = self.client.get(f'/api/events/{self.event1.id}/like/')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertTrue(get_res.data['isLiked'])
        self.assertEqual(get_res.data['likesCount'], 1)

        # Bob also likes event1
        self.client.force_authenticate(user=self.user2)
        res_bob = self.client.post(f'/api/events/{self.event1.id}/like/')
        self.assertEqual(res_bob.status_code, status.HTTP_200_OK)
        self.assertTrue(res_bob.data['isLiked'])
        self.assertEqual(res_bob.data['likesCount'], 2)

        # Alice unlikes event1
        self.client.force_authenticate(user=self.user1)
        res_unlike = self.client.post(f'/api/events/{self.event1.id}/like/')
        self.assertEqual(res_unlike.status_code, status.HTTP_200_OK)
        self.assertFalse(res_unlike.data['isLiked'])
        self.assertEqual(res_unlike.data['likesCount'], 1)

    def test_comment_creation_and_reply_hierarchy(self):
        # 1. Alice creates a top-level comment
        self.client.force_authenticate(user=self.user1)
        res = self.client.post(f'/api/events/{self.event1.id}/comments/', {
            'content': 'Are VIP passes going to include backstage access?'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['authorName'], 'Alice Smith')
        self.assertEqual(res.data['content'], 'Are VIP passes going to include backstage access?')
        self.assertIsNone(res.data['parentId'])
        comment1_id = res.data['id']

        # 2. Organizer replies to Alice's comment
        self.client.force_authenticate(user=self.organizer)
        reply_res = self.client.post(f'/api/events/{self.event1.id}/comments/', {
            'content': 'Yes Alice! VIP passes include complimentary backstage lounge access.',
            'parentId': comment1_id
        }, format='json')
        self.assertEqual(reply_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reply_res.data['parentId'], comment1_id)
        self.assertEqual(reply_res.data['authorName'], 'Master Host')
        self.assertTrue(reply_res.data['user']['isOrganizer'])
        reply1_id = reply_res.data['id']

        # 3. Bob also replies to the thread
        self.client.force_authenticate(user=self.user2)
        reply2_res = self.client.post(f'/api/events/{self.event1.id}/comments/', {
            'content': 'Awesome, grabbing my VIP pass right now!',
            'parentId': comment1_id
        }, format='json')
        self.assertEqual(reply2_res.status_code, status.HTTP_201_CREATED)

        # 4. Fetch comments list and verify nested structure
        list_res = self.client.get(f'/api/events/{self.event1.id}/comments/')
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(list_res.data['count'], 1)  # 1 top-level comment
        self.assertEqual(list_res.data['totalComments'], 3)  # 1 top-level + 2 replies
        top_comment = list_res.data['results'][0]
        self.assertEqual(top_comment['id'], comment1_id)
        self.assertEqual(len(top_comment['replies']), 2)
        self.assertEqual(top_comment['replies'][0]['id'], reply1_id)

    def test_prevent_cross_event_replies(self):
        # Alice comments on event 1
        self.client.force_authenticate(user=self.user1)
        res1 = self.client.post(f'/api/events/{self.event1.id}/comments/', {
            'content': 'Event 1 comment.'
        }, format='json')
        c1_id = res1.data['id']

        # Bob attempts to reply to event1's comment under event2
        self.client.force_authenticate(user=self.user2)
        invalid_res = self.client.post(f'/api/events/{self.event2.id}/comments/', {
            'content': 'Injected reply.',
            'parentId': c1_id
        }, format='json')
        self.assertEqual(invalid_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_and_delete_comment_permissions(self):
        # Alice comments on event 1
        self.client.force_authenticate(user=self.user1)
        res = self.client.post(f'/api/events/{self.event1.id}/comments/', {
            'content': 'Original comment content.'
        }, format='json')
        comment_id = res.data['id']

        # Bob attempts to edit Alice's comment (Forbidden 403)
        self.client.force_authenticate(user=self.user2)
        edit_forbidden = self.client.patch(f'/api/events/{self.event1.id}/comments/{comment_id}/', {
            'content': 'Hacked content.'
        }, format='json')
        self.assertEqual(edit_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # Alice successfully edits her own comment
        self.client.force_authenticate(user=self.user1)
        edit_success = self.client.patch(f'/api/events/{self.event1.id}/comments/{comment_id}/', {
            'content': 'Updated and clarified comment content.'
        }, format='json')
        self.assertEqual(edit_success.status_code, status.HTTP_200_OK)
        self.assertEqual(edit_success.data['content'], 'Updated and clarified comment content.')

        # Charlie attempts to delete Alice's comment (Forbidden 403)
        self.client.force_authenticate(user=self.user3)
        del_forbidden = self.client.delete(f'/api/events/{self.event1.id}/comments/{comment_id}/')
        self.assertEqual(del_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # Event Organizer deletes Alice's comment (Allowed 200 via soft delete)
        self.client.force_authenticate(user=self.organizer)
        del_success = self.client.delete(f'/api/events/{self.event1.id}/comments/{comment_id}/')
        self.assertEqual(del_success.status_code, status.HTTP_200_OK)
        self.assertTrue(del_success.data['isDeleted'])

        # Check comment in list is masked as deleted
        list_res = self.client.get(f'/api/events/{self.event1.id}/comments/')
        top_comment = list_res.data['results'][0]
        self.assertTrue(top_comment['isDeleted'])
        self.assertEqual(top_comment['content'], '[This comment was deleted by user]')

    def test_comment_like_toggle(self):
        # Alice creates comment
        self.client.force_authenticate(user=self.user1)
        res = self.client.post(f'/api/events/{self.event1.id}/comments/', {
            'content': 'Does the venue have free parking?'
        }, format='json')
        comment_id = res.data['id']

        # Bob likes Alice's comment
        self.client.force_authenticate(user=self.user2)
        like_res = self.client.post(f'/api/events/{self.event1.id}/comments/{comment_id}/like/')
        self.assertEqual(like_res.status_code, status.HTTP_200_OK)
        self.assertTrue(like_res.data['isLiked'])
        self.assertEqual(like_res.data['likeCount'], 1)

        # Bob unlikes Alice's comment
        unlike_res = self.client.post(f'/api/events/{self.event1.id}/comments/{comment_id}/like/')
        self.assertEqual(unlike_res.status_code, status.HTTP_200_OK)
        self.assertFalse(unlike_res.data['isLiked'])
        self.assertEqual(unlike_res.data['likeCount'], 0)

    def test_event_creation_with_staff_and_bulk_assignment(self):
        from accounts.models import StudioStaffMember
        from events.models import EventStaff

        # Login as organizer
        self.client.force_authenticate(user=self.organizer)

        # 1. Add user2 to studio staff roster
        StudioStaffMember.objects.create(
            organizer=self.organizer,
            user=self.user2,
            role_title='Lead Gate Inspector',
            default_can_view_attendees=True,
            default_can_check_in=True,
            default_can_edit_attendees=True
        )

        # 2. Create event with assigned staff IDs
        create_res = self.client.post('/api/events/manager/', {
            'title': 'Grand Symphony Night 2026',
            'category': 'Music & Concerts',
            'description': 'An evening of classical orchestral masterpieces in auditorium.',
            'date': '2026-11-20',
            'startTime': '19:00:00',
            'endTime': '22:00:00',
            'venueName': 'Symphony Hall',
            'city': 'Chandigarh',
            'status': 'published',
            'tiers': [{'name': 'Balcony', 'price': 40.0, 'capacity': 100}],
            'assignedStaffIds': [self.user2.id]
        }, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        new_event_id = create_res.data['id']

        # Verify staff was assigned automatically
        staff_qs = EventStaff.objects.filter(event_id=new_event_id, user=self.user2)
        self.assertTrue(staff_qs.exists())
        staff_rec = staff_qs.first()
        self.assertEqual(staff_rec.role_title, 'Lead Gate Inspector')
        self.assertTrue(staff_rec.can_check_in)
        self.assertTrue(staff_rec.can_edit_attendees)

        # 3. Test bulk assign endpoint
        bulk_res = self.client.post(f'/api/events/manager/{new_event_id}/staff/bulk-assign/', {
            'staffMembers': [
                {
                    'userId': self.user2.id,
                    'roleTitle': 'Stage Manager',
                    'canViewAttendees': True,
                    'canCheckIn': True,
                    'canEditAttendees': False
                }
            ]
        }, format='json')
        self.assertEqual(bulk_res.status_code, status.HTTP_201_CREATED)
        staff_rec.refresh_from_db()
        self.assertEqual(staff_rec.role_title, 'Stage Manager')
        self.assertFalse(staff_rec.can_edit_attendees)


class EventTicketingPolicyInheritanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            email='studio_owner@evento.com',
            password='Password123!',
            full_name='Studio Owner',
            role=MANAGER
        )
        # Create organizer profile with specific initial defaults
        self.profile = OrganizerProfile.objects.create(
            user=self.manager,
            organization_name='Starlight Studios',
            pass_platform_fee_to_buyer=False,
            allow_ticket_transfers=False,
            require_attendee_phone=True,
            auto_refund_cancelled_events=True
        )

        login_res = self.client.post('/api/auth/login/', {
            'email': 'studio_owner@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_event_inherits_organizer_defaults_when_unspecified(self):
        create_res = self.client.post('/api/events/manager/', {
            'title': 'Starlight Gala 2026',
            'category': 'Music & Concerts',
            'description': 'A grand orchestral gala night.',
            'date': '2026-12-01',
            'startTime': '19:00',
            'endTime': '22:00',
            'venueName': 'Starlight Arena',
            'city': 'Chandigarh',
            'status': 'published',
            'tiers': [{'name': 'General Admission', 'price': 50.0, 'capacity': 100}]
        }, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        event_id = create_res.data['id']

        # Verify event inherited the organizer profile defaults
        event = Event.objects.get(id=event_id)
        self.assertFalse(event.pass_platform_fee_to_buyer)
        self.assertFalse(event.allow_ticket_transfers)
        self.assertTrue(event.require_attendee_phone)
        self.assertTrue(event.auto_refund_cancelled_events)

        # Verify serializer outputs camelCase keys correctly
        self.assertFalse(create_res.data['passPlatformFeeToBuyer'])
        self.assertFalse(create_res.data['allowTicketTransfers'])
        self.assertTrue(create_res.data['requireAttendeePhone'])
        self.assertTrue(create_res.data['autoRefundCancelledEvents'])

    def test_global_profile_update_does_not_affect_existing_event(self):
        # 1. Create Event A with initial profile defaults (pass_fee=False, transfer=False)
        create_res = self.client.post('/api/events/manager/', {
            'title': 'Spring Fest 2026',
            'category': 'Music & Concerts',
            'description': 'Spring music celebration event.',
            'date': '2026-10-15',
            'startTime': '18:00',
            'venueName': 'Open Grounds',
            'city': 'Chandigarh',
            'status': 'published',
            'tiers': [{'name': 'GA', 'price': 30.0, 'capacity': 80}]
        }, format='json')
        event_a_id = create_res.data['id']
        event_a = Event.objects.get(id=event_a_id)
        self.assertFalse(event_a.pass_platform_fee_to_buyer)
        self.assertFalse(event_a.allow_ticket_transfers)

        # 2. Update Organizer Profile defaults via settings API to True
        settings_res = self.client.patch('/api/auth/settings/', {
            'passPlatformFeeToBuyer': True,
            'allowTicketTransfers': True,
        }, format='json')
        self.assertEqual(settings_res.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.pass_platform_fee_to_buyer)
        self.assertTrue(self.profile.allow_ticket_transfers)

        # 3. Verify Event A's snapshot remains locked (ISOLATED)
        event_a.refresh_from_db()
        self.assertFalse(event_a.pass_platform_fee_to_buyer)
        self.assertFalse(event_a.allow_ticket_transfers)

        # Check detail API for Event A
        detail_a = self.client.get(f'/api/events/manager/{event_a_id}/')
        self.assertEqual(detail_a.status_code, status.HTTP_200_OK)
        self.assertFalse(detail_a.data['passPlatformFeeToBuyer'])
        self.assertFalse(detail_a.data['allowTicketTransfers'])

        # 4. Create Event B -> should inherit the NEW profile defaults (pass_fee=True, transfer=True)
        create_b = self.client.post('/api/events/manager/', {
            'title': 'Autumn Fest 2026',
            'category': 'Music & Concerts',
            'description': 'Autumn music celebration event.',
            'date': '2026-11-15',
            'startTime': '18:00',
            'venueName': 'Open Grounds',
            'city': 'Chandigarh',
            'status': 'published',
            'tiers': [{'name': 'GA', 'price': 30.0, 'capacity': 80}]
        }, format='json')
        event_b_id = create_b.data['id']
        event_b = Event.objects.get(id=event_b_id)
        self.assertTrue(event_b.pass_platform_fee_to_buyer)
        self.assertTrue(event_b.allow_ticket_transfers)

    def test_explicit_policy_override_on_create_and_patch(self):
        # Explicitly supply custom policies when creating event
        create_res = self.client.post('/api/events/manager/', {
            'title': 'Custom Policy Stage',
            'category': 'Tech & Conferences',
            'description': 'Conference with custom fee and phone policies.',
            'date': '2026-12-10',
            'startTime': '09:00',
            'venueName': 'Tech Center',
            'city': 'Chandigarh',
            'status': 'published',
            'passPlatformFeeToBuyer': True,
            'allowTicketTransfers': True,
            'requireAttendeePhone': False,
            'autoRefundCancelledEvents': False,
            'tiers': [{'name': 'Attendee Pass', 'price': 100.0, 'capacity': 50}]
        }, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        event_id = create_res.data['id']

        event = Event.objects.get(id=event_id)
        self.assertTrue(event.pass_platform_fee_to_buyer)
        self.assertTrue(event.allow_ticket_transfers)
        self.assertFalse(event.require_attendee_phone)
        self.assertFalse(event.auto_refund_cancelled_events)

        # Now patch event - policy fields must remain immutable and unchanged from creation snapshot
        patch_res = self.client.patch(f'/api/events/manager/{event_id}/', {
            'title': 'Updated Tech Center Title',
            'passPlatformFeeToBuyer': False,
            'requireAttendeePhone': True
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertEqual(event.title, 'Updated Tech Center Title')
        # Creation-time policies are locked and preserved
        self.assertTrue(event.pass_platform_fee_to_buyer)
        self.assertFalse(event.require_attendee_phone)








