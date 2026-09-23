from rest_framework.permissions import BasePermission


class IsOrganizer(BasePermission):
    """
    Allows access only to authenticated users with an active OrganizerProfile capability.
    """
    message = "You must have an active Organizer Profile to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'is_organizer', False)
        )


# Backward compatibility alias
IsManagerUser = IsOrganizer
