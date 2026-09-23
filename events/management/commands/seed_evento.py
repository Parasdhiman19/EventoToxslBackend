from datetime import date, time, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, OrganizerProfile, SettlementAccount
from events.models import Event, TicketTier, SavedEvent
from tickets.models import Order, AttendeeTicket
from payouts.models import Payout


class Command(BaseCommand):
    help = 'Seeds initial realistic demo data for Evento platform'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Evento database..."))

        # 1. Create Organizer Manager
        manager, _ = User.objects.get_or_create(
            email='manager@evento.com',
            defaults={
                'full_name': 'Nexus Productions',
                'role': 'manager',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        manager.set_password('password123')
        manager.save()

        org_profile, _ = OrganizerProfile.objects.get_or_create(
            user=manager,
            defaults={
                'organization_name': 'Nexus Productions Studio',
                'handle': 'nexus_live',
                'support_email': 'contact@nexusproductions.io',
                'website': 'https://nexusproductions.io',
                'bio': 'Independent live music collective and urban arts event curators operating across Northern India.',
                'support_phone': '+91 98765 43210',
                'instagram': '@nexuslive',
            }
        )

        # Settlement Accounts
        SettlementAccount.objects.get_or_create(
            organizer=manager,
            bank_name='HDFC Bank Ltd',
            defaults={
                'account_number': '••••••••4819',
                'holder_name': 'Nexus Productions Studio',
                'account_type': 'Direct Settlement (Current A/C)',
                'status': 'Primary',
            }
        )
        SettlementAccount.objects.get_or_create(
            organizer=manager,
            bank_name='Stripe Direct Connect',
            defaults={
                'account_number': 'acct_1Nx4...99K',
                'holder_name': 'Nexus Productions LLC',
                'account_type': 'International Gateways',
                'status': 'Verified',
            }
        )

        # 2. Create Attendee User
        user, _ = User.objects.get_or_create(
            email='user@evento.com',
            defaults={
                'full_name': 'Jane Doe',
                'role': 'user',
            }
        )
        user.set_password('password123')
        user.save()

        # Extra buyers
        aarav, _ = User.objects.get_or_create(email='aarav.s@example.com', defaults={'full_name': 'Aarav Sharma', 'role': 'user'})
        elena, _ = User.objects.get_or_create(email='elena.r@studio.io', defaults={'full_name': 'Elena Rostova', 'role': 'user'})
        marcus, _ = User.objects.get_or_create(email='m.vance@techcorp.com', defaults={'full_name': 'Marcus Vance', 'role': 'user'})
        simran, _ = User.objects.get_or_create(email='simran.k@outlook.com', defaults={'full_name': 'Simran Kaur', 'role': 'user'})

        # 3. Create Events & Tiers
        events_spec = [
            {
                'title': 'Solstice Electronic & Indie Sessions 2026',
                'category': 'Music & Concerts',
                'description': 'An immersive dual-stage electronic audio-visual showcase featuring forward-thinking producers, analogue synth ensembles, and curated street gastronomy.',
                'banner_image': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1600&q=80',
                'date': date(2026, 8, 28),
                'start_time': time(20, 0),
                'venue_name': 'The Warehouse Stage • Hall B',
                'city': 'Chandigarh',
                'address': 'Industrial Area Phase 1, Chandigarh, Punjab',
                'is_featured': True,
                'status': 'published',
                'tiers': [
                    {'name': 'General Admission (Early)', 'price': Decimal('35.00'), 'capacity': 300, 'sold': 300, 'desc': 'Standard stage entry pass'},
                    {'name': 'General Admission (Phase 2)', 'price': Decimal('45.00'), 'capacity': 150, 'sold': 140, 'desc': 'Second release tickets'},
                    {'name': 'VIP Backstage Pass', 'price': Decimal('80.00'), 'capacity': 50, 'sold': 40, 'desc': 'Priority lane access + lounge entry'},
                ]
            },
            {
                'title': 'Modern Architecture & Design Summit',
                'category': 'Tech & Conferences',
                'description': 'A two-day gathering of global architects, structural designers, and sustainable urban visionaries.',
                'banner_image': 'https://images.unsplash.com/photo-1511578314322-379afb476865?auto=format&fit=crop&w=800&q=80',
                'date': date(2026, 9, 4),
                'start_time': time(10, 0),
                'venue_name': 'Metropolitan Art Center',
                'city': 'Delhi NCR',
                'address': 'Barakhamba Road, Connaught Place, Delhi NCR',
                'is_featured': False,
                'status': 'published',
                'tiers': [
                    {'name': 'General Delegate Access', 'price': Decimal('50.00'), 'capacity': 250, 'sold': 220, 'desc': 'Auditorium sessions & networking'},
                    {'name': 'All-Access Pass', 'price': Decimal('120.00'), 'capacity': 100, 'sold': 90, 'desc': 'Includes speaker dinner and workshops'},
                ]
            },
            {
                'title': 'Craft Coffee Roasters Expo & Cupping',
                'category': 'Food & Tasting',
                'description': 'Taste artisanal micro-lots from across the subcontinent and learn sensory cupping techniques.',
                'banner_image': 'https://images.unsplash.com/photo-1442512595331-e89e73853f31?auto=format&fit=crop&w=800&q=80',
                'date': date(2026, 9, 19),
                'start_time': time(11, 0),
                'venue_name': 'Riverside Pavilion',
                'city': 'Chandigarh',
                'address': 'Riverside Drive, Sector 1, Chandigarh',
                'is_featured': False,
                'status': 'published',
                'tiers': [
                    {'name': 'Standard Tasting Pass', 'price': Decimal('30.00'), 'capacity': 600, 'sold': 140, 'desc': 'Unlimited tasting samples'},
                ]
            },
            {
                'title': 'Underground Vinyl & Synth Sessions',
                'category': 'Nightlife',
                'description': 'All-vinyl analog sets in an intimate vault setting featuring deep minimal house and industrial techno.',
                'banner_image': 'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=800&q=80',
                'date': date(2026, 10, 2),
                'start_time': time(21, 30),
                'venue_name': 'The Baseway Vault',
                'city': 'Mohali',
                'address': 'Phase 7 Industrial Area, Mohali',
                'is_featured': False,
                'status': 'draft',
                'tiers': [
                    {'name': 'Early Bird Entry', 'price': Decimal('20.00'), 'capacity': 150, 'sold': 0, 'desc': 'Entry before 11 PM'},
                    {'name': 'Standard Entry', 'price': Decimal('35.00'), 'capacity': 100, 'sold': 0, 'desc': 'Anytime entry pass'},
                ]
            },
            {
                'title': 'Monochrome Photography Retrospective',
                'category': 'Art & Exhibitions',
                'description': 'A curated showcase of medium format silver gelatin architectural prints and street portraiture.',
                'banner_image': 'https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=800&q=80',
                'date': date(2026, 10, 14),
                'start_time': time(16, 0),
                'venue_name': 'Sector 8 Gallery Wing',
                'city': 'Chandigarh',
                'address': 'Inner Market, Sector 8, Chandigarh',
                'is_featured': False,
                'status': 'published',
                'tiers': [
                    {'name': 'Free General Admission', 'price': Decimal('0.00'), 'capacity': 100, 'sold': 15, 'desc': 'Complimentary gallery entry'},
                ]
            },
        ]

        created_events = []
        for spec in events_spec:
            event, _ = Event.objects.get_or_create(
                organizer=manager,
                title=spec['title'],
                defaults={
                    'category': spec['category'],
                    'description': spec['description'],
                    'banner_image': spec['banner_image'],
                    'date': spec['date'],
                    'start_time': spec['start_time'],
                    'venue_name': spec['venue_name'],
                    'city': spec['city'],
                    'address': spec['address'],
                    'is_featured': spec['is_featured'],
                    'status': spec['status'],
                }
            )
            created_events.append(event)

            for t_spec in spec['tiers']:
                tier, _ = TicketTier.objects.get_or_create(
                    event=event,
                    name=t_spec['name'],
                    defaults={
                        'price': t_spec['price'],
                        'capacity': t_spec['capacity'],
                        'sold_count': t_spec['sold'],
                        'description': t_spec['desc'],
                    }
                )

        # 4. Bookmarks for user
        SavedEvent.objects.get_or_create(user=user, event=created_events[0])
        SavedEvent.objects.get_or_create(user=user, event=created_events[3])

        # 5. Orders & Attendee Tickets
        solstice_event = created_events[0]
        vip_tier = solstice_event.tiers.filter(name__icontains='VIP').first() or solstice_event.tiers.first()
        arch_event = created_events[1]
        delegate_tier = arch_event.tiers.filter(name__icontains='Delegate').first() or arch_event.tiers.first()

        # Order 1 (Jane Doe)
        ord1, _ = Order.objects.get_or_create(
            order_number='ORD-882194',
            defaults={
                'user': user,
                'event': solstice_event,
                'tier': vip_tier,
                'quantity': 2,
                'unit_price': vip_tier.price,
                'fees': Decimal('5.60'),
                'total_amount': (vip_tier.price * 2) + Decimal('5.60'),
                'payment_method': 'UPI • Axis Bank',
                'status': 'Confirmed',
            }
        )
        AttendeeTicket.objects.get_or_create(
            ticket_code='EV-VIP-9021-01',
            defaults={
                'order': ord1,
                'event': solstice_event,
                'tier': vip_tier,
                'attendee_name': 'Jane Doe',
                'attendee_email': user.email,
                'seat_or_gate': 'Gate B • FastTrack',
                'is_checked_in': True,
                'checked_in_at': timezone.now() - timedelta(hours=2),
            }
        )
        AttendeeTicket.objects.get_or_create(
            ticket_code='EV-VIP-9021-02',
            defaults={
                'order': ord1,
                'event': solstice_event,
                'tier': vip_tier,
                'attendee_name': 'Jane Doe #2',
                'attendee_email': user.email,
                'seat_or_gate': 'Gate B • FastTrack',
                'is_checked_in': False,
            }
        )

        # Order 2 (Jane Doe)
        ord2, _ = Order.objects.get_or_create(
            order_number='ORD-774102',
            defaults={
                'user': user,
                'event': arch_event,
                'tier': delegate_tier,
                'quantity': 1,
                'unit_price': delegate_tier.price,
                'fees': Decimal('2.50'),
                'total_amount': delegate_tier.price + Decimal('2.50'),
                'payment_method': 'Mastercard •• 4120',
                'status': 'Confirmed',
            }
        )
        AttendeeTicket.objects.get_or_create(
            ticket_code='EV-DEL-8842-44',
            defaults={
                'order': ord2,
                'event': arch_event,
                'tier': delegate_tier,
                'attendee_name': 'Jane Doe',
                'attendee_email': user.email,
                'seat_or_gate': 'Hall A • Row 4',
                'is_checked_in': False,
            }
        )

        # Orders from other customers
        ord_aarav, _ = Order.objects.get_or_create(
            order_number='ORD-99214',
            defaults={
                'user': aarav,
                'event': solstice_event,
                'tier': vip_tier,
                'quantity': 2,
                'unit_price': vip_tier.price,
                'fees': Decimal('5.60'),
                'total_amount': Decimal('165.60'),
                'payment_method': 'UPI • Axis Bank',
                'status': 'Paid',
            }
        )
        AttendeeTicket.objects.get_or_create(
            ticket_code='EV-VIP-9021-88',
            defaults={
                'order': ord_aarav,
                'event': solstice_event,
                'tier': vip_tier,
                'attendee_name': 'Aarav Sharma',
                'attendee_email': aarav.email,
                'seat_or_gate': 'Gate B • FastTrack',
                'is_checked_in': True,
                'checked_in_at': timezone.now() - timedelta(hours=3),
            }
        )

        ord_elena, _ = Order.objects.get_or_create(
            order_number='ORD-99213',
            defaults={
                'user': elena,
                'event': arch_event,
                'tier': delegate_tier,
                'quantity': 1,
                'unit_price': delegate_tier.price,
                'fees': Decimal('1.75'),
                'total_amount': Decimal('51.75'),
                'payment_method': 'Mastercard •• 4120',
                'status': 'Paid',
            }
        )
        AttendeeTicket.objects.get_or_create(
            ticket_code='EV-DEL-8842-12',
            defaults={
                'order': ord_elena,
                'event': arch_event,
                'tier': delegate_tier,
                'attendee_name': 'Elena Rostova',
                'attendee_email': elena.email,
                'seat_or_gate': 'Main Deck',
                'is_checked_in': True,
                'checked_in_at': timezone.now() - timedelta(hours=1),
            }
        )

        # 6. Payout History
        hdfc = SettlementAccount.objects.filter(organizer=manager, bank_name__icontains='HDFC').first()
        Payout.objects.get_or_create(
            payout_number='PO-88219',
            defaults={
                'organizer': manager,
                'settlement_account': hdfc,
                'gross_amount': Decimal('14200.00'),
                'fee_deducted': Decimal('0.00'),
                'net_disbursed': Decimal('14200.00'),
                'utr_reference': 'UTR-9921840192',
                'status': 'Completed',
            }
        )
        Payout.objects.get_or_create(
            payout_number='PO-88204',
            defaults={
                'organizer': manager,
                'settlement_account': hdfc,
                'gross_amount': Decimal('9850.00'),
                'fee_deducted': Decimal('0.00'),
                'net_disbursed': Decimal('9850.00'),
                'utr_reference': 'UTR-8192301948',
                'status': 'Completed',
            }
        )

        self.stdout.write(self.style.SUCCESS("Evento database seeded successfully with demo organizer and attendee data!"))
