from rest_framework import status, views
from rest_framework.response import Response

from accounts.models import OrganizerProfile, SettlementAccount, StudioStaffMember
from accounts.permissions import IsManagerUser
from accounts.serializers import (
    OrganizerProfileSerializer,
    SettlementAccountSerializer,
    StudioStaffMemberSerializer,
    AddStudioStaffMemberSerializer,
)


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
