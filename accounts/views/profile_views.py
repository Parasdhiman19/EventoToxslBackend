from rest_framework import status, views, permissions
from rest_framework.response import Response

from accounts.serializers import (
    UserSerializer,
    UserProfileUpdateSerializer,
    ChangePasswordSerializer,
    BecomeOrganizerSerializer,
)


class BecomeOrganizerView(views.APIView):
    """
    Attaches an OrganizerProfile to the currently authenticated user, activating organizer capability.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BecomeOrganizerSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            request.user.refresh_from_db()

            # Notify user that organizer profile is now active
            try:
                from notifications.services import NotificationService
                NotificationService.send_organizer_profile_activated(request.user)
            except Exception:
                pass

            return Response({
                'user': UserSerializer(request.user).data,
                'message': 'Organizer capability activated successfully.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        request.user.refresh_from_db()
        return Response(UserSerializer(request.user, context={'request': request}).data)

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(
            instance=request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            user = serializer.save()
            user.refresh_from_db()
            return Response({
                'user': UserSerializer(user, context={'request': request}).data,
                'message': 'Profile updated successfully.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()

            # Notify user of password change
            try:
                from notifications.services import NotificationService
                NotificationService.send_password_changed(request.user)
            except Exception:
                pass

            return Response({
                'message': 'Password changed successfully.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
