from decimal import Decimal
from django.db import transaction
from rest_framework import serializers
from .models import Order, AttendeeTicket
from events.models import Event, TicketTier


class AttendeeTicketSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='ticket_code', read_only=True)
    ticketCode = serializers.CharField(source='ticket_code', read_only=True)
    barcode = serializers.CharField(source='ticket_code', read_only=True)
    orderId = serializers.CharField(source='order.order_number', read_only=True)
    eventTitle = serializers.CharField(source='event.title', read_only=True)
    event = serializers.CharField(source='event.title', read_only=True)
    organizer = serializers.SerializerMethodField()
    tier = serializers.CharField(source='tier.name', read_only=True)
    price = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    doorsOpen = serializers.SerializerMethodField()
    showStarts = serializers.SerializerMethodField()
    venue = serializers.CharField(source='event.venue_name', read_only=True)
    address = serializers.CharField(source='event.address', read_only=True)
    gate = serializers.SerializerMethodField()
    seatOrGate = serializers.SerializerMethodField()
    seat = serializers.SerializerMethodField()
    seatRow = serializers.SerializerMethodField()
    seatNumber = serializers.SerializerMethodField()
    sectionName = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    attendeeName = serializers.CharField(source='attendee_name', read_only=True)
    name = serializers.CharField(source='attendee_name', read_only=True)
    email = serializers.CharField(source='attendee_email', read_only=True)
    checkedIn = serializers.BooleanField(source='is_checked_in', read_only=True)
    checkInTime = serializers.SerializerMethodField()
    orderDate = serializers.SerializerMethodField()

    class Meta:
        model = AttendeeTicket
        fields = (
            'id', 'ticketCode', 'barcode', 'orderId', 'eventTitle', 'event',
            'organizer', 'tier', 'price', 'date', 'doorsOpen', 'showStarts',
            'venue', 'address', 'gate', 'seatOrGate', 'seat', 'seatRow',
            'seatNumber', 'sectionName', 'status', 'attendeeName',
            'name', 'email', 'checkedIn', 'checkInTime', 'orderDate'
        )

    def get_organizer(self, obj):
        if hasattr(obj.event.organizer, 'organizer_profile') and obj.event.organizer.organizer_profile.organization_name:
            return obj.event.organizer.organizer_profile.organization_name
        return obj.event.organizer.full_name or "Nexus Productions"

    def get_price(self, obj):
        return f"${obj.tier.price:,.2f}"

    def get_date(self, obj):
        return obj.event.date.strftime('%b %d, %Y') if obj.event.date else ''

    def get_doorsOpen(self, obj):
        return obj.event.start_time.strftime('%I:%M %p') if obj.event.start_time else ''

    def get_showStarts(self, obj):
        return obj.event.start_time.strftime('%I:%M %p') if obj.event.start_time else ''

    def get_gate(self, obj):
        if hasattr(obj, 'assigned_seat') and obj.assigned_seat:
            s = obj.assigned_seat
            return f"Row {s.row} • Seat {s.seat_number}"
        return obj.seat_or_gate

    def get_seatOrGate(self, obj):
        if hasattr(obj, 'assigned_seat') and obj.assigned_seat:
            s = obj.assigned_seat
            return f"{s.section_name} - Row {s.row}, Seat {s.seat_number}"
        return obj.seat_or_gate

    def get_seat(self, obj):
        if hasattr(obj, 'assigned_seat') and obj.assigned_seat:
            s = obj.assigned_seat
            return f"Row {s.row}, Seat {s.seat_number}"
        return None

    def get_seatRow(self, obj):
        if hasattr(obj, 'assigned_seat') and obj.assigned_seat:
            return obj.assigned_seat.row
        return None

    def get_seatNumber(self, obj):
        if hasattr(obj, 'assigned_seat') and obj.assigned_seat:
            return obj.assigned_seat.seat_number
        return None

    def get_sectionName(self, obj):
        if hasattr(obj, 'assigned_seat') and obj.assigned_seat:
            return obj.assigned_seat.section_name
        return None

    def get_status(self, obj):
        return 'past' if obj.event.is_ended or obj.event.computed_status == 'past' else 'upcoming'

    def get_checkInTime(self, obj):
        return obj.checked_in_at.strftime('%I:%M %p') if obj.checked_in_at else None

    def get_orderDate(self, obj):
        return obj.created_at.strftime('%b %d, %Y') if obj.created_at else ''


class OrderSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='order_number', read_only=True)
    date = serializers.SerializerMethodField()
    time = serializers.SerializerMethodField()
    eventTitle = serializers.CharField(source='event.title', read_only=True)
    event = serializers.CharField(source='event.title', read_only=True)
    organizer = serializers.SerializerMethodField()
    tier = serializers.CharField(source='tier.name', read_only=True)
    unitPrice = serializers.SerializerMethodField()
    fees = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    paymentMethod = serializers.CharField(source='payment_method', read_only=True)
    venue = serializers.CharField(source='event.venue_name', read_only=True)
    eventDate = serializers.SerializerMethodField()
    ticketIds = serializers.SerializerMethodField()
    customer = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    qty = serializers.IntegerField(source='quantity', read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'date', 'time', 'eventTitle', 'event', 'organizer', 'tier',
            'quantity', 'qty', 'unitPrice', 'fees', 'total', 'paymentMethod',
            'status', 'venue', 'eventDate', 'ticketIds', 'customer', 'email'
        )

    def get_date(self, obj):
        return obj.created_at.strftime('%b %d, %Y')

    def get_time(self, obj):
        return obj.created_at.strftime('%I:%M %p')

    def get_organizer(self, obj):
        if hasattr(obj.event.organizer, 'organizer_profile') and obj.event.organizer.organizer_profile.organization_name:
            return obj.event.organizer.organizer_profile.organization_name
        return obj.event.organizer.full_name or "Nexus Productions"

    def get_unitPrice(self, obj):
        return f"${obj.unit_price:,.2f}"

    def get_fees(self, obj):
        return f"${obj.fees:,.2f}"

    def get_total(self, obj):
        return f"${obj.total_amount:,.2f}"

    def get_eventDate(self, obj):
        return obj.event.date.strftime('%b %d, %Y') if obj.event.date else ''

    def get_ticketIds(self, obj):
        return list(obj.tickets.values_list('ticket_code', flat=True))


class CheckoutSerializer(serializers.Serializer):
    eventId = serializers.IntegerField(required=False)
    event_id = serializers.IntegerField(required=False)
    tierId = serializers.IntegerField(required=False)
    tier_id = serializers.IntegerField(required=False)
    seatIds = serializers.ListField(child=serializers.IntegerField(), required=False)
    seat_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    quantity = serializers.IntegerField(min_value=1, default=1)
    paymentMethod = serializers.CharField(required=False, default='UPI • Axis Bank')
    payment_method = serializers.CharField(required=False, default='UPI • Axis Bank')
    attendeeName = serializers.CharField(required=False, allow_blank=True)
    attendee_name = serializers.CharField(required=False, allow_blank=True)
    attendeeEmail = serializers.EmailField(required=False, allow_blank=True)
    attendee_email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        from events.models import Seat

        event_id = attrs.get('eventId') or attrs.get('event_id')
        tier_id = attrs.get('tierId') or attrs.get('tier_id')
        seat_ids = attrs.get('seatIds') or attrs.get('seat_ids') or []

        if not event_id:
            raise serializers.ValidationError({"eventId": "Event ID is required."})

        event = Event.objects.filter(pk=event_id).first()
        if not event:
            raise serializers.ValidationError({"eventId": "Event not found."})

        if event.status == 'draft':
            raise serializers.ValidationError({"eventId": "This event is not published."})

        if event.is_ended or event.status == 'past':
            raise serializers.ValidationError({"eventId": "This event has ended and tickets can no longer be purchased."})

        # If seats are selected
        seat_objs = []
        if seat_ids:
            seat_objs = list(Seat.objects.filter(id__in=seat_ids, event=event).select_related('tier'))
            if len(seat_objs) != len(seat_ids):
                raise serializers.ValidationError({"seatIds": "One or more selected seats could not be found for this event."})

            for s in seat_objs:
                if s.status != 'available':
                    raise serializers.ValidationError({"seatIds": f"Seat {s.row}-{s.seat_number} is no longer available."})

            attrs['quantity'] = len(seat_objs)
            # Infer primary tier from first seat if not explicitly provided
            if not tier_id and seat_objs[0].tier:
                tier = seat_objs[0].tier
            elif tier_id:
                tier = TicketTier.objects.filter(pk=tier_id, event=event).first()
            else:
                tier = event.tiers.first()
        else:
            if not tier_id:
                raise serializers.ValidationError({"tierId": "Ticket tier ID is required."})
            tier = TicketTier.objects.filter(pk=tier_id, event=event).first()
            if not tier:
                raise serializers.ValidationError({"tierId": "Ticket tier not found for this event."})

            quantity = attrs.get('quantity', 1)
            remaining = tier.capacity - tier.sold_count
            if quantity > remaining:
                raise serializers.ValidationError({"quantity": f"Only {remaining} tickets remaining in this tier."})

        attrs['event_obj'] = event
        attrs['tier_obj'] = tier
        attrs['seat_objs'] = seat_objs
        attrs['seat_ids'] = seat_ids
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        from events.models import Seat

        user = validated_data['user']
        event = validated_data['event_obj']
        tier_id = validated_data['tier_obj'].id
        seat_ids = validated_data.get('seat_ids') or []

        # Lock ticket tier row for update
        tier = TicketTier.objects.select_for_update().get(pk=tier_id)

        payment_method = validated_data.get('paymentMethod') or validated_data.get('payment_method') or 'UPI • Axis Bank'
        attendee_name = (
            validated_data.get('attendeeName') or
            validated_data.get('attendee_name') or
            getattr(user, 'full_name', '') or
            "Guest Attendee"
        )
        attendee_email = (
            validated_data.get('attendeeEmail') or
            validated_data.get('attendee_email') or
            user.email
        )

        if seat_ids:
            # Lock seats atomically to prevent race condition
            locked_seats = list(
                Seat.objects.select_for_update().filter(id__in=seat_ids, event=event).select_related('tier')
            )
            if len(locked_seats) != len(seat_ids):
                raise serializers.ValidationError({"seatIds": "Selected seats could not be found."})

            for s in locked_seats:
                if s.status != 'available':
                    raise serializers.ValidationError({"seatIds": f"Seat {s.row}-{s.seat_number} was just booked by another attendee. Please choose different seats."})

            quantity = len(locked_seats)
            # Calculate total from individual seat tiers
            subtotal = sum((s.tier.price if s.tier else tier.price) for s in locked_seats)
            unit_price = (subtotal / quantity) if quantity > 0 else tier.price
            pass_fee = getattr(event, 'pass_platform_fee_to_buyer', True)
            fees = (subtotal * Decimal('0.035')).quantize(Decimal('0.01')) if (pass_fee and subtotal > 0) else Decimal('0.00')
            total_amount = subtotal + fees

            # Create Order
            order = Order.objects.create(
                user=user,
                event=event,
                tier=tier,
                quantity=quantity,
                unit_price=unit_price,
                fees=fees,
                total_amount=total_amount,
                payment_method=payment_method,
                status='Confirmed'
            )

            # Generate Attendee Tickets and attach to seats
            tier_counts = {}
            for i, seat in enumerate(locked_seats):
                seat_tier = seat.tier or tier
                ticket = AttendeeTicket.objects.create(
                    order=order,
                    event=event,
                    tier=seat_tier,
                    attendee_name=f"{attendee_name} #{i+1}" if quantity > 1 else attendee_name,
                    attendee_email=attendee_email,
                    seat_or_gate=f"Row {seat.row} • Seat {seat.seat_number}"
                )
                seat.status = 'booked'
                seat.booked_by = user
                seat.order = order
                seat.ticket = ticket
                seat.save()

                tier_counts[seat_tier.id] = tier_counts.get(seat_tier.id, 0) + 1

            # Update sold_count for all affected tiers
            for t_id, cnt in tier_counts.items():
                t_obj = TicketTier.objects.select_for_update().get(pk=t_id)
                t_obj.sold_count += cnt
                t_obj.save()

            return order

        else:
            # Standard non-assigned seating flow
            quantity = validated_data.get('quantity', 1)
            remaining = tier.capacity - tier.sold_count
            if quantity > remaining:
                raise serializers.ValidationError({"quantity": f"Only {remaining} tickets remaining in this tier."})

            unit_price = tier.price
            subtotal = unit_price * quantity
            pass_fee = getattr(event, 'pass_platform_fee_to_buyer', True)
            fees = (subtotal * Decimal('0.035')).quantize(Decimal('0.01')) if (pass_fee and subtotal > 0) else Decimal('0.00')
            total_amount = subtotal + fees

            order = Order.objects.create(
                user=user,
                event=event,
                tier=tier,
                quantity=quantity,
                unit_price=unit_price,
                fees=fees,
                total_amount=total_amount,
                payment_method=payment_method,
                status='Confirmed'
            )

            for i in range(quantity):
                AttendeeTicket.objects.create(
                    order=order,
                    event=event,
                    tier=tier,
                    attendee_name=f"{attendee_name} #{i+1}" if quantity > 1 else attendee_name,
                    attendee_email=attendee_email,
                    seat_or_gate="Gate B • FastTrack" if "VIP" in tier.name.upper() else "Main Gate Entrance"
                )

            tier.sold_count += quantity
            tier.save()

            return order

