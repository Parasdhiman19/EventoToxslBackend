from rest_framework.permissions import BasePermission
from .models import Event, EventStaff


class IsEventManager(BasePermission):
    """
    Allows access only to authenticated users who own/created the event.
    """
    message = "You must be the manager of this event to perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Event):
            return obj.organizer == request.user
        elif hasattr(obj, 'event'):
            return obj.event.organizer == request.user
        return False


def check_event_staff_permission(user, event, permission_name=None):
    """
    Helper function to check if a user is either:
    1. The Event Organizer / Manager (always has full permissions).
    2. An assigned EventStaff member with the given permission enabled.
    """
    if not user or not user.is_authenticated:
        return False

    # Event manager always has full authority
    if event.organizer == user:
        return True

    # Check staff record
    staff = EventStaff.objects.filter(event=event, user=user).first()
    if not staff:
        return False

    if permission_name:
        return bool(getattr(staff, permission_name, False))

    return True
