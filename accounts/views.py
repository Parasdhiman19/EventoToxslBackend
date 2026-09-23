from rest_framework import status, views, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from .models import OrganizerProfile, SettlementAccount, StudioStaffMember
from .permissions import IsManagerUser
from .serializers import (
    UserSerializer,
    SignupSerializer,
    LoginSerializer,
    OrganizerProfileSerializer,
    SettlementAccountSerializer,
    BecomeOrganizerSerializer,
    StudioStaffMemberSerializer,
    AddStudioStaffMemberSerializer,
)

COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    } 


def set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        samesite='Lax',
        secure=False,  # Set to True in HTTPS production
        max_age=COOKIE_MAX_AGE,
        path='/',
    )


class SignupView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            tokens = get_tokens_for_user(user)

            response = Response({
                'user': UserSerializer(user).data,
                'access': tokens['access'],
                'message': 'Account created successfully.'
            }, status=status.HTTP_201_CREATED)

            # Store refresh token exclusively in HttpOnly cookie
            set_refresh_cookie(response, tokens['refresh'])
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = get_tokens_for_user(user)

            response = Response({
                'user': UserSerializer(user).data,
                'access': tokens['access'],
                'message': 'Logged in successfully.'
            }, status=status.HTTP_200_OK)

            # Store refresh token exclusively in HttpOnly cookie
            set_refresh_cookie(response, tokens['refresh'])
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenRefreshView(views.APIView):
    """
    Reads the refresh token from HttpOnly cookie and returns a fresh access token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = (
            request.COOKIES.get('refresh_token') or 
            request.data.get('refresh') or 
            request.data.get('refreshToken') or
            request.data.get('refresh_token')
        )

        if not refresh_token:
            return Response(
                {'detail': 'Authentication refresh cookie not found.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)

            response = Response({
                'access': new_access_token,
            }, status=status.HTTP_200_OK)
            return response
        except (TokenError, InvalidToken):
            response = Response(
                {'detail': 'Refresh token is invalid or expired.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
            response.delete_cookie('refresh_token', path='/')
            return response


class LogoutView(views.APIView):
    """
    Clears the HttpOnly refresh token cookie on the backend.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        response = Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        response.delete_cookie('refresh_token', path='/')
        return response


class BecomeOrganizerView(views.APIView):
    """
    Attaches an OrganizerProfile to the currently authenticated user, activating organizer capability.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BecomeOrganizerSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            # Refetch/refresh user from db to ensure properties are fresh
            request.user.refresh_from_db()
            return Response({
                'user': UserSerializer(request.user).data,
                'message': 'Organizer capability activated successfully.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        request.user.refresh_from_db()
        return Response(UserSerializer(request.user).data)


class OrganizerSettingsView(views.APIView):
    permission_classes = [IsManagerUser]

    def get_profile(self, user):
        profile, _ = OrganizerProfile.objects.get_or_create(
            user=user,
            defaults={
                'organization_name': f"{user.full_name}'s Studio" if user.full_name else 'Nexus Productions Studio',
            }
        )
        return profile

    def get(self, request):
        profile = self.get_profile(request.user)
        accounts = SettlementAccount.objects.filter(organizer=request.user)
        return Response({
            'profile': OrganizerProfileSerializer(profile, context={'request': request}).data,
            'settlementAccounts': SettlementAccountSerializer(accounts, many=True).data,
        })

    def patch(self, request):
        profile = self.get_profile(request.user)
        serializer = OrganizerProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                'profile': serializer.data,
                'message': 'Settings saved successfully.'
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SettlementAccountListView(views.APIView):
    permission_classes = [IsManagerUser]

    def get(self, request):
        accounts = SettlementAccount.objects.filter(organizer=request.user)
        return Response(SettlementAccountSerializer(accounts, many=True).data)

    def post(self, request):
        serializer = SettlementAccountSerializer(data=request.data)
        if serializer.is_valid():
            # If this is the first account, make it primary automatically
            existing_count = SettlementAccount.objects.filter(organizer=request.user).count()
            is_primary = serializer.validated_data.get('is_primary', False) or existing_count == 0
            serializer.save(organizer=request.user, is_primary=is_primary)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SettlementAccountDetailView(views.APIView):
    permission_classes = [IsManagerUser]

    def patch(self, request, pk):
        account = SettlementAccount.objects.filter(pk=pk, organizer=request.user).first()
        if not account:
            return Response({'detail': 'Settlement account not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SettlementAccountSerializer(account, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        account = SettlementAccount.objects.filter(pk=pk, organizer=request.user).first()
        if not account:
            return Response({'detail': 'Settlement account not found.'}, status=status.HTTP_404_NOT_FOUND)
        was_primary = account.is_primary
        account.delete()

        # If deleted account was primary, set another account as primary if available
        if was_primary:
            next_account = SettlementAccount.objects.filter(organizer=request.user).first()
            if next_account:
                next_account.is_primary = True
                next_account.save()

        return Response({'detail': 'Settlement account removed successfully.'})


class StudioStaffListView(views.APIView):
    permission_classes = [IsManagerUser]

    def get(self, request):
        staff_qs = StudioStaffMember.objects.filter(organizer=request.user).select_related('user')
        return Response(StudioStaffMemberSerializer(staff_qs, many=True, context={'request': request}).data)

    def post(self, request):
        serializer = AddStudioStaffMemberSerializer(
            data=request.data,
            context={'request': request, 'organizer': request.user}
        )
        if serializer.is_valid():
            record = serializer.save()
            return Response(StudioStaffMemberSerializer(record, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudioStaffDetailView(views.APIView):
    permission_classes = [IsManagerUser]

    def patch(self, request, pk):
        staff = StudioStaffMember.objects.filter(pk=pk, organizer=request.user).first()
        if not staff:
            return Response({'detail': 'Studio staff member not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        if 'roleTitle' in data or 'role_title' in data:
            staff.role_title = (data.get('roleTitle') or data.get('role_title') or '').strip() or staff.role_title
        if 'defaultCanViewAttendees' in data or 'default_can_view_attendees' in data:
            staff.default_can_view_attendees = bool(data.get('defaultCanViewAttendees', data.get('default_can_view_attendees')))
        if 'defaultCanCheckIn' in data or 'default_can_check_in' in data:
            staff.default_can_check_in = bool(data.get('defaultCanCheckIn', data.get('default_can_check_in')))
        if 'defaultCanEditAttendees' in data or 'default_can_edit_attendees' in data:
            staff.default_can_edit_attendees = bool(data.get('defaultCanEditAttendees', data.get('default_can_edit_attendees')))
        if 'phone' in data:
            staff.phone = (data.get('phone') or '').strip()
        if 'notes' in data:
            staff.notes = (data.get('notes') or '').strip()

        staff.save()
        return Response(StudioStaffMemberSerializer(staff, context={'request': request}).data)

    def delete(self, request, pk):
        staff = StudioStaffMember.objects.filter(pk=pk, organizer=request.user).first()
        if not staff:
            return Response({'detail': 'Studio staff member not found.'}, status=status.HTTP_404_NOT_FOUND)
        staff.delete()
        return Response({'detail': 'Staff member removed from studio directory successfully.'})

