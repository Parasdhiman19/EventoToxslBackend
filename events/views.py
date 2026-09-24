from django.utils import timezone
from django.db import transaction
from rest_framework import status, views, permissions
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q

from accounts.permissions import IsManagerUser
from .models import Event, SavedEvent, EventLike, EventComment, CommentLike
from .utils.media_utils import upload_image_to_cloudinary
from .serializers import (
    PublicEventListSerializer,
    PublicEventDetailSerializer,
    ManagerEventListSerializer,
    ManagerEventDetailSerializer,
    EventListSerializer,
    EventDetailSerializer,
    EventCreateUpdateSerializer,
    CommentSerializer,
    CommentCreateSerializer,
)


def get_active_events_condition():
    """
    Returns Q expression for active (upcoming/ongoing) published events.
    """
    now = timezone.localtime(timezone.now()) if timezone.is_aware(timezone.now()) else timezone.now()
    current_date = now.date()
    current_time = now.time()

    return Q(status='published') & (
        Q(date__gt=current_date) |
        Q(date=current_date, end_time__isnull=False, end_time__gt=current_time) |
        Q(date=current_date, end_time__isnull=True, start_time__gte=current_time)
    )


class PublicEventListView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # Exclude expired/ended events from public discovery and prefetch related relations
        queryset = Event.objects.filter(get_active_events_condition()).select_related(
            'organizer' , 'organizer__organizer_profile'
        ).prefetch_related('tiers', 'likes', 'comments', 'saved_by')

        category = request.query_params.get('category')
        if category and category != 'All':
            queryset = queryset.filter(category__iexact=category)

        city = request.query_params.get('city')
        if city and city != 'All Cities':
            queryset = queryset.filter(city__iexact=city)

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(venue_name__icontains=search) |
                Q(city__icontains=search) |
                Q(organizer__full_name__icontains=search)
            )

        sort_by = request.query_params.get('sort') or request.query_params.get('ordering')
        if sort_by == 'recent':
            queryset = queryset.order_by('-created_at')
        elif sort_by == 'upcoming' or sort_by == 'date_asc':
            queryset = queryset.order_by('date', 'start_time')
        elif sort_by == 'featured':
            queryset = queryset.order_by('-is_featured', 'date', 'start_time')

        page_param = request.query_params.get('page')
        if page_param:
            try:
                page_num = max(1, int(page_param))
            except ValueError:
                page_num = 1

            try:
                page_size = int(request.query_params.get('page_size', 10))
            except ValueError:
                page_size = 10

            page_size = max(1, min(page_size, 50))
            from django.core.paginator import Paginator, EmptyPage
            paginator = Paginator(queryset, page_size)
            try:
                page_obj = paginator.page(page_num)
                serialized_events = PublicEventListSerializer(page_obj.object_list, many=True, context={'request': request}).data
            except EmptyPage:
                serialized_events = []

            return Response({
                'count': paginator.count,
                'totalPages': paginator.num_pages,
                'currentPage': page_num,
                'pageSize': page_size,
                'hasMore': page_num < paginator.num_pages,
                'results': serialized_events,
            })

        serializer = PublicEventListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class FeaturedHeroEventView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # Select active featured hero
        active_events = Event.objects.filter(get_active_events_condition())
        hero = active_events.filter(is_featured=True).first()
        if not hero:
            hero = active_events.first()
        if not hero:
            return Response(None)
        return Response(PublicEventDetailSerializer(hero, context={'request': request}).data)


class EventDetailView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            event = Event.objects.get(pk=pk)
            return Response(PublicEventDetailSerializer(event, context={'request': request}).data)
        except Event.DoesNotExist:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)


class ManagerEventListCreateView(views.APIView):
    permission_classes = [IsManagerUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        status_tab = request.query_params.get('status', 'all')
        now = timezone.localtime(timezone.now()) if timezone.is_aware(timezone.now()) else timezone.now()
        current_date = now.date()
        current_time = now.time()

        if status_tab == 'staff':
            queryset = Event.objects.filter(staff_members__user=request.user).exclude(organizer=request.user).distinct()
        elif status_tab == 'all':
            queryset = Event.objects.filter(
                Q(organizer=request.user) | Q(staff_members__user=request.user)
            ).distinct()
        else:
            queryset = Event.objects.filter(organizer=request.user)

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(venue_name__icontains=search) |
                Q(id__icontains=search)
            )

        if status_tab == 'published':
            # Active / Upcoming published events
            queryset = queryset.filter(
                Q(status='published') & (
                    Q(date__gt=current_date) |
                    Q(date=current_date, end_time__isnull=False, end_time__gt=current_time) |
                    Q(date=current_date, end_time__isnull=True, start_time__gte=current_time)
                )
            )
        elif status_tab == 'draft':
            queryset = queryset.filter(status='draft')
        elif status_tab == 'past':
            # Explicitly past/archived OR published events whose date/time has passed
            queryset = queryset.filter(
                Q(status='past') |
                (
                    Q(status='published') & (
                        Q(date__lt=current_date) |
                        Q(date=current_date, end_time__isnull=False, end_time__lte=current_time) |
                        Q(date=current_date, end_time__isnull=True, start_time__lt=current_time)
                    )
                )
            )

        serializer = ManagerEventListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = EventCreateUpdateSerializer(data=request.data)


        
        if serializer.is_valid():
            event = serializer.save(organizer=request.user)
            return Response(ManagerEventDetailSerializer(event, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ManagerEventDetailView(views.APIView):
    permission_classes = [IsManagerUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, pk, user):
        from .models import EventStaff
        return Event.objects.filter(
            Q(pk=pk, organizer=user) | Q(pk=pk, staff_members__user=user)
        ).distinct().first()

    def get(self, request, pk):
        event = self.get_object(pk, request.user)
        if not event:
            return Response({'detail': 'Event not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ManagerEventDetailSerializer(event, context={'request': request}).data)

    def patch(self, request, pk):
        event = Event.objects.filter(pk=pk, organizer=request.user).first()
        if not event:
            return Response({'detail': 'Event not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = EventCreateUpdateSerializer(event, data=request.data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(ManagerEventDetailSerializer(updated, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        event = Event.objects.filter(pk=pk, organizer=request.user).first()
        if not event:
            return Response({'detail': 'Event not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)

        permanent = request.query_params.get('permanent', '').lower() in ['true', '1']
        if permanent:
            has_sales = event.orders.filter(status__in=['Confirmed', 'Paid', 'Completed', 'Refunded']).exists()
            has_attendees = event.attendees.exists()
            has_sold_tiers = event.tiers.filter(sold_count__gt=0).exists()

            if has_sales or has_attendees or has_sold_tiers:
                return Response(
                    {
                        'detail': 'Cannot permanently delete an event with confirmed ticket sales, attendee passports, or financial transactions. Please archive or end the event instead to preserve financial and attendee records.',
                        'can_delete': False,
                        'has_sales': True,
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            event.delete()
            return Response({'detail': 'Event permanently deleted successfully.', 'deleted': True})

        event.status = 'past'
        event.save()
        return Response({'detail': 'Event archived and ended successfully.', 'status': 'past', 'archived': True})


class UserSavedEventsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        saved_events = Event.objects.filter(saved_by__user=request.user)
        serializer = PublicEventListSerializer(saved_events, many=True, context={'request': request})
        return Response(serializer.data)


class ToggleBookmarkView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, event_id):
        event = Event.objects.filter(pk=event_id).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        bookmark = SavedEvent.objects.filter(user=request.user, event=event).first()
        if bookmark:
            bookmark.delete()
            return Response({'isBookmarked': False, 'message': 'Removed from saved stages.'})
        else:
            SavedEvent.objects.create(user=request.user, event=event)
            return Response({'isBookmarked': True, 'message': 'Saved to your bookmarked stages.'})


class ClearBookmarksView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        SavedEvent.objects.filter(user=request.user).delete()
        return Response({'message': 'All saved stages cleared.'})


# ==========================================
# EVENT STAFF MANAGEMENT (ORGANIZER ONLY)
# ==========================================

class ManagerEventStaffListView(views.APIView):
    """
    Manager endpoint to list all assigned staff or add a staff member to an event.
    """
    permission_classes = [IsManagerUser]

    def get(self, request, event_id):
        from .models import EventStaff
        from .serializers import EventStaffSerializer

        event = Event.objects.filter(pk=event_id, organizer=request.user).first()
        if not event:
            return Response({'detail': 'Event not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        staff_members = EventStaff.objects.filter(event=event).select_related('user')
        return Response(EventStaffSerializer(staff_members, many=True).data)

    def post(self, request, event_id):
        from .serializers import AddEventStaffSerializer, EventStaffSerializer

        event = Event.objects.filter(pk=event_id, organizer=request.user).first()
        if not event:
            return Response({'detail': 'Event not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AddEventStaffSerializer(
            data=request.data,
            context={'event': event, 'request': request}
        )
        if serializer.is_valid():
            staff_record = serializer.save()
            return Response(EventStaffSerializer(staff_record).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ManagerEventStaffDetailView(views.APIView):
    """
    Manager endpoint to modify staff permissions or remove staff from an event.
    """
    permission_classes = [IsManagerUser]

    def patch(self, request, event_id, staff_id):
        from .models import EventStaff
        from .serializers import EventStaffSerializer

        event = Event.objects.filter(pk=event_id, organizer=request.user).first()
        if not event:
            return Response({'detail': 'Event not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        staff = EventStaff.objects.filter(pk=staff_id, event=event).first()
        if not staff:
            return Response({'detail': 'Staff assignment not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        if 'roleTitle' in data or 'role_title' in data:
            staff.role_title = (data.get('roleTitle') or data.get('role_title') or '').strip() or staff.role_title
        if 'canViewAttendees' in data or 'can_view_attendees' in data:
            staff.can_view_attendees = bool(data.get('canViewAttendees', data.get('can_view_attendees')))
        if 'canCheckIn' in data or 'can_check_in' in data:
            staff.can_check_in = bool(data.get('canCheckIn', data.get('can_check_in')))
        if 'canEditAttendees' in data or 'can_edit_attendees' in data:
            staff.can_edit_attendees = bool(data.get('canEditAttendees', data.get('can_edit_attendees')))

        staff.save()
        return Response(EventStaffSerializer(staff).data)

    def delete(self, request, event_id, staff_id):
        from .models import EventStaff

        event = Event.objects.filter(pk=event_id, organizer=request.user).first()
        if not event:
            return Response({'detail': 'Event not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        staff = EventStaff.objects.filter(pk=staff_id, event=event).first()
        if not staff:
            return Response({'detail': 'Staff assignment not found.'}, status=status.HTTP_404_NOT_FOUND)

        staff.delete()
        return Response({'detail': 'Staff member removed from event successfully.'})


class ManagerEventStaffBulkAssignView(views.APIView):
    """
    Manager endpoint to bulk assign studio staff members to a specific event.
    """
    permission_classes = [IsManagerUser]

    def post(self, request, event_id):
        from .serializers import BulkAssignEventStaffSerializer, EventStaffSerializer

        event = Event.objects.filter(pk=event_id, organizer=request.user).first()
        if not event:
            return Response({'detail': 'Event not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = BulkAssignEventStaffSerializer(data=request.data, context={'event': event, 'request': request})
        if serializer.is_valid():
            records = serializer.save()
            return Response(EventStaffSerializer(records, many=True).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ManagerUserSearchView(views.APIView):
    """
    Manager endpoint to search registered active users to assign as staff.
    """
    permission_classes = [IsManagerUser]

    def get(self, request):
        from django.contrib.auth import get_user_model
        from .serializers import StaffUserSearchSerializer

        User = get_user_model()
        query = (request.query_params.get('q') or '').strip()

        if len(query) < 2:
            return Response([])

        users = User.objects.filter(
            Q(email__icontains=query) | Q(full_name__icontains=query),
            is_active=True
        ).filter(
            Q(role='manager') | Q(organizer_profile__isnull=False)
        ).distinct().exclude(pk=request.user.pk)[:15]

        return Response(StaffUserSearchSerializer(users, many=True).data)


class ManagerStaffOverviewView(views.APIView):
    """
    Manager endpoint to list all team members / staff across all events hosted by the organizer.
    """
    permission_classes = [IsManagerUser]

    def get(self, request):
        from .models import EventStaff
        from accounts.models import StudioStaffMember

        # 1. Fetch saved studio staff
        studio_staff_qs = StudioStaffMember.objects.filter(organizer=request.user).select_related('user')
        members_map = {}

        for sm in studio_staff_qs:
            u_id = sm.user.id
            name = sm.user.full_name or sm.user.email.split('@')[0].title()
            initials = ''.join([part[0].upper() for part in name.split()[:2]]) or 'ST'
            members_map[u_id] = {
                'id': u_id,
                'studioStaffId': sm.id,
                'name': name,
                'email': sm.user.email,
                'avatar': initials,
                'role': sm.role_title or 'Stage Coordinator',
                'roleTitle': sm.role_title or 'Stage Coordinator',
                'phone': sm.phone,
                'notes': sm.notes,
                'defaultCanViewAttendees': sm.default_can_view_attendees,
                'defaultCanCheckIn': sm.default_can_check_in,
                'defaultCanEditAttendees': sm.default_can_edit_attendees,
                'assignedEvents': [],
            }

        # 2. Fetch event staff assignments
        staff_qs = EventStaff.objects.filter(event__organizer=request.user).select_related('user', 'event')
        for s in staff_qs:
            u_id = s.user.id
            if u_id not in members_map:
                name = s.user.full_name or s.user.email.split('@')[0].title()
                initials = ''.join([part[0].upper() for part in name.split()[:2]]) or 'ST'
                members_map[u_id] = {
                    'id': u_id,
                    'studioStaffId': None,
                    'name': name,
                    'email': s.user.email,
                    'avatar': initials,
                    'role': s.role_title or 'Stage Coordinator',
                    'roleTitle': s.role_title or 'Stage Coordinator',
                    'phone': '',
                    'notes': '',
                    'defaultCanViewAttendees': s.can_view_attendees,
                    'defaultCanCheckIn': s.can_check_in,
                    'defaultCanEditAttendees': s.can_edit_attendees,
                    'assignedEvents': [],
                }
            members_map[u_id]['assignedEvents'].append({
                'eventId': s.event.id,
                'eventTitle': s.event.title,
                'staffRecordId': s.id,
                'roleTitle': s.role_title or members_map[u_id]['roleTitle'],
            })

        owner_name = request.user.full_name or request.user.email.split('@')[0].title()
        owner_initials = ''.join([part[0].upper() for part in owner_name.split()[:2]]) or 'OW'

        team_list = [{
            'id': request.user.id,
            'name': f"{owner_name} (You)",
            'email': request.user.email,
            'avatar': owner_initials,
            'role': 'Owner & Studio Admin',
            'roleTitle': 'Owner & Studio Admin',
            'access': 'Full Access',
            'isOwner': True,
            'assignedEventsCount': Event.objects.filter(organizer=request.user).count(),
        }]

        for u_id, m in members_map.items():
            if u_id != request.user.id:
                m['isOwner'] = False
                m['assignedEventsCount'] = len(m['assignedEvents'])
                m['access'] = f"{m['roleTitle']} ({len(m['assignedEvents'])} Event{'s' if len(m['assignedEvents']) != 1 else ''})"
                team_list.append(m)

        return Response(team_list)



# ==========================================
# STAFF PORTAL (ASSIGNED USER VIEW)
# ==========================================

class StaffAssignedEventsListView(views.APIView):
    """
    Staff endpoint for authenticated users to list events they are assigned to work as staff.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import EventStaff
        from .serializers import StaffAssignedEventSerializer

        assigned_event_ids = EventStaff.objects.filter(user=request.user).values_list('event_id', flat=True)
        events = Event.objects.filter(id__in=assigned_event_ids).order_by('-date')

        search = request.query_params.get('search')
        if search:
            events = events.filter(
                Q(title__icontains=search) |
                Q(venue_name__icontains=search) |
                Q(city__icontains=search)
            )

        serializer = StaffAssignedEventSerializer(events, many=True, context={'request': request})
        return Response(serializer.data)


# ==========================================
# SEATING LAYOUT & VENUE MAP ENDPOINTS
# ==========================================

class ManagerEventSeatingView(views.APIView):
    """
    Manager endpoint to fetch and update seating layout and individual seat structure.
    """
    permission_classes = [IsManagerUser]

    def get(self, request, event_id):
        from .serializers import SeatSerializer, TicketTierSerializer
        event = Event.objects.filter(pk=event_id, organizer=request.user).first()
        if not event:
            return Response({'detail': 'Event not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        seats = event.seats.all().select_related('tier')
        return Response({
            'eventId': event.id,
            'title': event.title,
            'hasAssignedSeating': event.has_assigned_seating,
            'seatingLayout': event.seating_layout or {},
            'seats': SeatSerializer(seats, many=True).data,
            'tiers': TicketTierSerializer(event.tiers.all(), many=True).data,
        })

    def post(self, request, event_id):
        from .serializers import sync_seating_layout_to_db, SeatSerializer, TicketTierSerializer
        event = Event.objects.filter(pk=event_id, organizer=request.user).first()
        if not event:
            return Response({'detail': 'Event not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        layout_data = request.data.get('seatingLayout') or request.data.get('seating_layout') or request.data
        if not layout_data or not isinstance(layout_data, dict):
            return Response({'detail': 'Invalid seating layout payload.'}, status=status.HTTP_400_BAD_REQUEST)

        sync_seating_layout_to_db(event, layout_data)

        seats = event.seats.all().select_related('tier')
        return Response({
            'detail': 'Seating layout saved and synchronized successfully.',
            'eventId': event.id,
            'hasAssignedSeating': event.has_assigned_seating,
            'seatingLayout': event.seating_layout,
            'seats': SeatSerializer(seats, many=True).data,
            'tiers': TicketTierSerializer(event.tiers.all(), many=True).data,
        })


class PublicEventSeatingView(views.APIView):
    """
    Public attendee endpoint to inspect active seating map, availability, and tier pricing.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, event_id):
        from .serializers import SeatSerializer, TicketTierSerializer
        event = Event.objects.filter(pk=event_id).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        seats = event.seats.all().select_related('tier')
        return Response({
            'eventId': event.id,
            'title': event.title,
            'hasAssignedSeating': event.has_assigned_seating,
            'seatingLayout': event.seating_layout or {},
            'seats': SeatSerializer(seats, many=True).data,
            'tiers': TicketTierSerializer(event.tiers.all(), many=True).data,
        })


# ==========================================
# SOCIAL INTERACTION VIEWS (LIKES & COMMENTS)
# ==========================================

class EventLikeToggleView(views.APIView):
    """
    Endpoint to retrieve or toggle user like status on an event.
    """
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request, event_id):
        event = Event.objects.filter(pk=event_id).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_liked = False
        if request.user.is_authenticated:
            is_liked = event.likes.filter(user=request.user).exists()

        return Response({
            'eventId': event.id,
            'isLiked': is_liked,
            'likesCount': event.likes.count(),
        })

    def post(self, request, event_id):
        event = Event.objects.filter(pk=event_id).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            like_obj = EventLike.objects.filter(user=request.user, event=event).first()
            if like_obj:
                like_obj.delete()
                is_liked = False
                msg = "Removed like from stage."
            else:
                EventLike.objects.create(user=request.user, event=event)
                is_liked = True
                msg = "Liked stage."

        return Response({
            'eventId': event.id,
            'isLiked': is_liked,
            'likesCount': event.likes.count(),
            'message': msg,
        })


class EventCommentListCreateView(views.APIView):
    """
    Endpoint to list paginated top-level comments and replies, or create a new comment/reply.
    """
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request, event_id):
        event = Event.objects.filter(pk=event_id).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        comments_qs = EventComment.objects.filter(
            event=event,
            parent__isnull=True
        ).select_related('user').prefetch_related(
            'likes',
            'replies',
            'replies__user',
            'replies__likes'
        ).order_by('-created_at')

        page_param = request.query_params.get('page', 1)
        try:
            page_num = max(1, int(page_param))
        except ValueError:
            page_num = 1

        try:
            page_size = int(request.query_params.get('page_size', 20))
        except ValueError:
            page_size = 20
        page_size = max(1, min(page_size, 50))

        from django.core.paginator import Paginator, EmptyPage
        paginator = Paginator(comments_qs, page_size)
        try:
            page_obj = paginator.page(page_num)
            serialized_comments = CommentSerializer(
                page_obj.object_list,
                many=True,
                context={'request': request, 'include_replies': True}
            ).data
        except EmptyPage:
            serialized_comments = []

        total_active_comments = event.comments.filter(is_deleted=False).count()

        return Response({
            'eventId': event.id,
            'count': paginator.count,
            'totalComments': total_active_comments,
            'totalPages': paginator.num_pages,
            'currentPage': page_num,
            'pageSize': page_size,
            'hasMore': page_num < paginator.num_pages,
            'results': serialized_comments,
        })

    def post(self, request, event_id):
        event = Event.objects.filter(pk=event_id).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CommentCreateSerializer(data=request.data, context={'event': event, 'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        parent_id = serializer.validated_data.get('parentId')
        parent_comment = None
        if parent_id:
            parent_comment = EventComment.objects.filter(pk=parent_id, event=event).first()
            if not parent_comment:
                return Response({'detail': 'Parent comment not found for this event.'}, status=status.HTTP_400_BAD_REQUEST)

        comment = EventComment.objects.create(
            event=event,
            user=request.user,
            parent=parent_comment,
            content=serializer.validated_data['content']
        )

        return Response(
            CommentSerializer(comment, context={'request': request, 'include_replies': True}).data,
            status=status.HTTP_201_CREATED
        )


class EventCommentDetailView(views.APIView):
    """
    Endpoint for comment authors to edit comments or authors/organizers to soft-delete comments.
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, event_id, comment_id):
        comment = EventComment.objects.filter(pk=comment_id, event_id=event_id).first()
        if not comment:
            return Response({'detail': 'Comment not found.'}, status=status.HTTP_404_NOT_FOUND)

        if comment.user_id != request.user.id:
            return Response({'detail': 'You do not have permission to edit this comment.'}, status=status.HTTP_403_FORBIDDEN)

        if comment.is_deleted:
            return Response({'detail': 'Cannot edit a deleted comment.'}, status=status.HTTP_400_BAD_REQUEST)

        content = request.data.get('content', '').strip()
        if not content:
            return Response({'content': ['Comment content cannot be empty.']}, status=status.HTTP_400_BAD_REQUEST)
        if len(content) > 1000:
            return Response({'content': ['Comment cannot exceed 1000 characters.']}, status=status.HTTP_400_BAD_REQUEST)

        comment.content = content
        comment.save(update_fields=['content', 'updated_at'])

        return Response(CommentSerializer(comment, context={'request': request}).data)

    def delete(self, request, event_id, comment_id):
        comment = EventComment.objects.filter(pk=comment_id, event_id=event_id).select_related('event').first()
        if not comment:
            return Response({'detail': 'Comment not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_author = comment.user_id == request.user.id
        is_organizer = comment.event.organizer_id == request.user.id

        if not (is_author or is_organizer):
            return Response({'detail': 'You do not have permission to delete this comment.'}, status=status.HTTP_403_FORBIDDEN)

        comment.is_deleted = True
        comment.save(update_fields=['is_deleted', 'updated_at'])

        return Response({'detail': 'Comment deleted successfully.', 'isDeleted': True})


class CommentLikeToggleView(views.APIView):
    """
    Endpoint to toggle user like on a specific comment.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, event_id, comment_id):
        comment = EventComment.objects.filter(pk=comment_id, event_id=event_id).first()
        if not comment:
            return Response({'detail': 'Comment not found.'}, status=status.HTTP_404_NOT_FOUND)

        if comment.is_deleted:
            return Response({'detail': 'Cannot like a deleted comment.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            like_obj = CommentLike.objects.filter(user=request.user, comment=comment).first()
            if like_obj:
                like_obj.delete()
                is_liked = False
            else:
                CommentLike.objects.create(user=request.user, comment=comment)
                is_liked = True

        return Response({
            'commentId': comment.id,
            'isLiked': is_liked,
            'likeCount': comment.likes.count(),
        })


class ImageUploadView(views.APIView):
    """
    POST /api/events/upload/image/
    Universal image upload endpoint for event banners, studio logos, and profile artwork.
    Uploads directly to Cloudinary and returns the permanent HTTPS CDN URL.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        uploaded_file = (
            request.FILES.get('image') or
            request.FILES.get('file') or
            request.FILES.get('banner') or
            request.FILES.get('logo') or
            request.data.get('image') or
            request.data.get('file') or
            request.data.get('banner') or
            request.data.get('logo')
        )

        if not uploaded_file:
            return Response(
                {'detail': 'No image file provided in request.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Folder can be 'banners', 'logos', 'avatars', etc.
        raw_folder = request.data.get('folder', 'banners')
        clean_folder = 'evento/' + str(raw_folder).strip().strip('/')

        try:
            cdn_url = upload_image_to_cloudinary(uploaded_file, folder=clean_folder)
            if not cdn_url:
                return Response(
                    {'detail': 'Failed to process image file. Please ensure it is a valid image.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response({
                'url': cdn_url,
                'secure_url': cdn_url,
                'message': 'Image uploaded successfully.'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'detail': f'Upload failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



