from events.models import EventStaff
from accounts.models import StudioStaffMember, User


def sync_event_staff_ids(event, staff_user_ids):
    """
    Synchronizes EventStaff assignments for an event based on selected staff user IDs.
    Inherits default roles/permissions from the organizer's StudioStaffMember directory if available.
    """
    if staff_user_ids is None:
        return

    clean_ids = set()
    for uid in staff_user_ids:
        try:
            val = int(uid)
            if val != event.organizer_id:
                clean_ids.add(val)
        except (ValueError, TypeError):
            pass

    studio_staff_map = {
        sm.user_id: sm
        for sm in StudioStaffMember.objects.filter(organizer=event.organizer, user_id__in=clean_ids)
    }

    existing_staff_records = {s.user_id: s for s in EventStaff.objects.filter(event=event)}

    # Remove unselected staff
    for uid, staff_obj in existing_staff_records.items():
        if uid not in clean_ids:
            staff_obj.delete()

    # Create or retain selected staff
    for uid in clean_ids:
        studio_member = studio_staff_map.get(uid)
        role_title = studio_member.role_title if studio_member else 'Stage Coordinator'
        can_view = studio_member.default_can_view_attendees if studio_member else True
        can_check = studio_member.default_can_check_in if studio_member else True
        can_edit = studio_member.default_can_edit_attendees if studio_member else False

        if uid in existing_staff_records:
            staff_obj = existing_staff_records[uid]
            if not staff_obj.role_title and role_title:
                staff_obj.role_title = role_title
                staff_obj.save(update_fields=['role_title'])
        else:
            u_obj = User.objects.filter(pk=uid, is_active=True).first()
            if u_obj:
                EventStaff.objects.create(
                    event=event,
                    user=u_obj,
                    role_title=role_title,
                    can_view_attendees=can_view,
                    can_check_in=can_check,
                    can_edit_attendees=can_edit
                )
