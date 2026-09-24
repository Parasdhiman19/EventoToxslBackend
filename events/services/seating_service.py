from decimal import Decimal
from events.models import TicketTier, Seat


def sync_seating_layout_to_db(event, seating_layout):
    """
    Parses seating_layout JSON and synchronizes TicketTier and Seat models.
    Updates capacities, pricing, seat coordinates, and status.
    """
    if not seating_layout or not isinstance(seating_layout, dict):
        return

    # 1. Update event layout field
    event.seating_layout = seating_layout
    event.has_assigned_seating = True
    event.save(update_fields=['seating_layout', 'has_assigned_seating'])

    tiers_config = seating_layout.get('tiers', [])
    grid = seating_layout.get('grid', [])

    # Calculate capacity per tier from the grid
    tier_counts = {}
    for seat_data in grid:
        if not seat_data or seat_data.get('status') == 'empty' or seat_data.get('isAisle') or seat_data.get('is_aisle'):
            continue
        tier_name = (seat_data.get('tierName') or seat_data.get('tier') or 'General Admission').strip()
        tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1

    # Map or create TicketTiers
    existing_tiers = {t.name.lower(): t for t in event.tiers.all()}
    tier_model_map = {}

    for t_conf in tiers_config:
        t_name = (t_conf.get('name') or 'General Admission').strip()
        raw_price = t_conf.get('price', 0)
        try:
            price = Decimal(str(raw_price).replace('$', '').strip()) if raw_price not in [None, ''] else Decimal('0.00')
        except Exception:
            price = Decimal('0.00')
        desc = t_conf.get('description', '') or ''
        cap = max(1, tier_counts.get(t_name, t_conf.get('capacity', 100)))

        if t_name.lower() in existing_tiers:
            tier_obj = existing_tiers[t_name.lower()]
            tier_obj.price = price
            tier_obj.capacity = max(cap, tier_obj.sold_count)
            tier_obj.description = desc
            tier_obj.save()
        else:
            tier_obj = TicketTier.objects.create(
                event=event,
                name=t_name,
                price=price,
                capacity=cap,
                description=desc
            )
        tier_model_map[t_name.lower()] = tier_obj

    # Fallback: if no tiers_config defined but grid has seats
    for t_name, count in tier_counts.items():
        if t_name.lower() not in tier_model_map:
            if t_name.lower() in existing_tiers:
                tier_obj = existing_tiers[t_name.lower()]
                tier_obj.capacity = max(count, tier_obj.sold_count)
                tier_obj.save()
            else:
                tier_obj = TicketTier.objects.create(
                    event=event,
                    name=t_name,
                    price=Decimal('35.00'),
                    capacity=count,
                    description='Standard Seating'
                )
            tier_model_map[t_name.lower()] = tier_obj

    # Synchronize Seats
    existing_seats = {
        (s.section_name, s.row, str(s.seat_number)): s
        for s in event.seats.all()
    }
    active_seat_keys = set()

    for seat_data in grid:
        if not seat_data or seat_data.get('status') == 'empty' or seat_data.get('isAisle') or seat_data.get('is_aisle'):
            continue

        sec = seat_data.get('sectionName') or seat_data.get('section_name') or 'Main Hall'
        row = str(seat_data.get('row', '')).strip()
        num = str(seat_data.get('seatNumber') or seat_data.get('seat_number') or seat_data.get('col', '')).strip()
        if not row or not num:
            continue

        key = (sec, row, num)
        active_seat_keys.add(key)
        t_name = (seat_data.get('tierName') or seat_data.get('tier') or 'General Admission').strip().lower()
        tier_obj = tier_model_map.get(t_name) or event.tiers.first()
        is_acc = bool(seat_data.get('isAccessible') or seat_data.get('is_accessible'))
        raw_status = seat_data.get('status', 'available')
        seat_status = raw_status if raw_status in ['available', 'reserved', 'booked', 'blocked'] else 'available'

        if key in existing_seats:
            seat_obj = existing_seats[key]
            # Don't overwrite if seat is already booked/sold
            if seat_obj.status != 'booked':
                seat_obj.tier = tier_obj
                seat_obj.status = seat_status
                seat_obj.is_accessible = is_acc
                seat_obj.save()
        else:
            Seat.objects.create(
                event=event,
                tier=tier_obj,
                section_name=sec,
                row=row,
                seat_number=num,
                status=seat_status,
                is_accessible=is_acc
            )

    # Delete obsolete seats that are not booked
    for key, seat_obj in existing_seats.items():
        if key not in active_seat_keys and seat_obj.status != 'booked':
            seat_obj.delete()
