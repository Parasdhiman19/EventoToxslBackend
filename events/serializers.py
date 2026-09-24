import json
from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from .models import Event, TicketTier, SavedEvent, EventLike, EventComment, CommentLike
from .utils.media_utils import upload_image_to_cloudinary, resolve_image_url, format_relative_time
from .services.seating_service import sync_seating_layout_to_db
from .services.staff_service import sync_event_staff_ids, sync_event_staff_ids as _sync_event_staff_ids



class PublicTicketTierSerializer(serializers.ModelSerializer):
    """
    Public-safe ticket tier serializer for attendee discovery and booking.
    Excludes soldCount, gross earnings, and internal inventory limits.
    """
    tierName = serializers.CharField(source='name', read_only=True)
    isSoldOut = serializers.SerializerMethodField()
    is_sold_out = serializers.SerializerMethodField()

    class Meta:
        model = TicketTier
        fields = ('id', 'name', 'tierName', 'price', 'description', 'isSoldOut', 'is_sold_out')

    def get_isSoldOut(self, obj):
        return obj.capacity > 0 and obj.sold_count >= obj.capacity

    def get_is_sold_out(self, obj):
        return obj.capacity > 0 and obj.sold_count >= obj.capacity


class ManagerTicketTierSerializer(serializers.ModelSerializer):
    """
    Manager-only ticket tier serializer with full financial metrics & sales count.
    """
    tierName = serializers.CharField(source='name', read_only=True)
    soldCount = serializers.IntegerField(source='sold_count', read_only=True)
    gross = serializers.SerializerMethodField()

    class Meta:
        model = TicketTier
        fields = ('id', 'name', 'tierName', 'price', 'capacity', 'sold_count', 'soldCount', 'description', 'gross')

    def get_gross(self, obj):
        return f"${(obj.price * obj.sold_count):,.2f}"


TicketTierSerializer = ManagerTicketTierSerializer


class SeatSerializer(serializers.ModelSerializer):
    tierName = serializers.CharField(source='tier.name', read_only=True)
    tierId = serializers.IntegerField(source='tier.id', read_only=True)
    price = serializers.SerializerMethodField()
    priceRaw = serializers.SerializerMethodField()
    seatCode = serializers.SerializerMethodField()
    sectionName = serializers.CharField(source='section_name', read_only=True)
    seatNumber = serializers.CharField(source='seat_number', read_only=True)
    isAccessible = serializers.BooleanField(source='is_accessible', read_only=True)

    status = serializers.SerializerMethodField()

    class Meta:
        from .models import Seat
        model = Seat
        fields = (
            'id', 'section_name', 'sectionName', 'row', 'seat_number', 'seatNumber',
            'status', 'is_accessible', 'isAccessible', 'tier', 'tierId',
            'tierName', 'price', 'priceRaw', 'seatCode'
        )

    def get_status(self, obj):
        from django.utils import timezone
        if obj.status == 'reserved' and obj.reserved_until:
            if obj.reserved_until < timezone.now():
                return 'available'
        return obj.status

    def get_price(self, obj):
        if obj.tier and obj.tier.price is not None:
            return f"${obj.tier.price:,.2f}"
        return "$0.00"

    def get_priceRaw(self, obj):
        if obj.tier and obj.tier.price is not None:
            return float(obj.tier.price)
        return 0.0

    def get_seatCode(self, obj):
        return f"{obj.row}-{obj.seat_number}"





class PublicEventListSerializer(serializers.ModelSerializer):
    """
    Public discovery event serializer.
    Excludes sensitive financial metrics (grossRevenue, ticketsSold, totalCapacity, staff permissions).
    """
    organizer = serializers.SerializerMethodField()
    venue = serializers.CharField(source='venue_name', read_only=True)
    venueName = serializers.CharField(source='venue_name', read_only=True)
    time = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    dateFormatted = serializers.SerializerMethodField()
    startTime = serializers.SerializerMethodField()
    endTime = serializers.SerializerMethodField()
    startingPrice = serializers.SerializerMethodField()
    priceRange = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    banner = serializers.SerializerMethodField()
    banner_image = serializers.SerializerMethodField()
    isBookmarked = serializers.SerializerMethodField()
    likesCount = serializers.SerializerMethodField()
    isLiked = serializers.SerializerMethodField()
    commentsCount = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    isEnded = serializers.SerializerMethodField()
    is_ended = serializers.SerializerMethodField()
    hasAssignedSeating = serializers.BooleanField(source='has_assigned_seating', read_only=True)

    class Meta:
        model = Event
        fields = (
            'id', 'title', 'organizer', 'category', 'date', 'dateFormatted',
            'time', 'start_time', 'startTime', 'end_time', 'endTime',
            'city', 'venue', 'venueName', 'venue_name', 'address', 'is_online',
            'startingPrice', 'priceRange', 'image', 'banner', 'banner_image',
            'status', 'isEnded', 'is_ended', 'is_featured', 'isBookmarked',
            'likesCount', 'isLiked', 'commentsCount',
            'has_assigned_seating', 'hasAssignedSeating'
        )

    def get_status(self, obj):
        return obj.computed_status

    def get_isEnded(self, obj):
        return obj.is_ended

    def get_is_ended(self, obj):
        return obj.is_ended

    def get_image(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_banner(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_banner_image(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_organizer(self, obj):
        try:
            if hasattr(obj.organizer, 'organizer_profile') and obj.organizer.organizer_profile:
                if obj.organizer.organizer_profile.organization_name:
                    return obj.organizer.organizer_profile.organization_name
        except Exception:
            pass
        return getattr(obj.organizer, 'full_name', '') or "Nexus Productions"

    def get_time(self, obj):
        return obj.start_time.strftime('%I:%M %p') if obj.start_time else ''

    def get_date(self, obj):
        return str(obj.date) if obj.date else ''

    def get_dateFormatted(self, obj):
        return obj.date.strftime('%b %d, %Y') if obj.date else ''

    def get_startTime(self, obj):
        return obj.start_time.strftime('%H:%M') if obj.start_time else ''

    def get_endTime(self, obj):
        return obj.end_time.strftime('%H:%M') if obj.end_time else ''

    def get_startingPrice(self, obj):
        tiers = obj.tiers.all()
        if not tiers.exists():
            return 'Free'
        min_price = min(t.price for t in tiers)
        return f"${min_price:,.2f}" if min_price > 0 else 'Free Entry'

    def get_priceRange(self, obj):
        tiers = obj.tiers.all()
        if not tiers.exists():
            return 'Free'
        prices = [t.price for t in tiers]
        min_p, max_p = min(prices), max(prices)
        if min_p == max_p:
            return f"${min_p:,.2f}" if min_p > 0 else 'Free'
        return f"${min_p:,.0f} – ${max_p:,.0f}"

    def get_isBookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return SavedEvent.objects.filter(user=request.user, event=obj).exists()
        return False

    def get_likesCount(self, obj):
        return obj.likes.count()

    def get_isLiked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_commentsCount(self, obj):
        return obj.comments.filter(is_deleted=False).count()


class PublicEventDetailSerializer(serializers.ModelSerializer):
    """
    Public-safe event detail serializer for attendee stage viewing and booking.
    Uses PublicTicketTierSerializer to hide gross sales and sold counts.
    """
    organizer = serializers.SerializerMethodField()
    venue = serializers.CharField(source='venue_name', read_only=True)
    venueName = serializers.CharField(source='venue_name', read_only=True)
    time = serializers.SerializerMethodField()
    dateFormatted = serializers.SerializerMethodField()
    startTime = serializers.SerializerMethodField()
    endTime = serializers.SerializerMethodField()
    startingPrice = serializers.SerializerMethodField()
    priceRange = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    banner = serializers.SerializerMethodField()
    banner_image = serializers.SerializerMethodField()
    tiers = PublicTicketTierSerializer(many=True, read_only=True)
    isBookmarked = serializers.SerializerMethodField()
    likesCount = serializers.SerializerMethodField()
    isLiked = serializers.SerializerMethodField()
    commentsCount = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    isEnded = serializers.SerializerMethodField()
    is_ended = serializers.SerializerMethodField()
    hasAssignedSeating = serializers.BooleanField(source='has_assigned_seating', read_only=True)
    seatingLayout = serializers.JSONField(source='seating_layout', read_only=True)
    allowTicketTransfers = serializers.BooleanField(source='allow_ticket_transfers', read_only=True)
    requireAttendeePhone = serializers.BooleanField(source='require_attendee_phone', read_only=True)
    autoRefundCancelledEvents = serializers.BooleanField(source='auto_refund_cancelled_events', read_only=True)

    class Meta:
        model = Event
        fields = (
            'id', 'title', 'organizer', 'category', 'description', 'date', 'dateFormatted',
            'start_time', 'end_time', 'startTime', 'endTime', 'time',
            'venue_name', 'venueName', 'venue', 'city', 'address',
            'is_online', 'status', 'isEnded', 'is_ended', 'is_featured', 'image', 'banner', 'banner_image',
            'startingPrice', 'priceRange', 'tiers', 'isBookmarked', 'likesCount', 'isLiked', 'commentsCount',
            'has_assigned_seating', 'hasAssignedSeating', 'seating_layout', 'seatingLayout',
            'allow_ticket_transfers', 'allowTicketTransfers',
            'require_attendee_phone', 'requireAttendeePhone',
            'auto_refund_cancelled_events', 'autoRefundCancelledEvents',
        )

    def get_status(self, obj):
        return obj.computed_status

    def get_isEnded(self, obj):
        return obj.is_ended

    def get_is_ended(self, obj):
        return obj.is_ended

    def get_image(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_banner(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_banner_image(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_organizer(self, obj):
        try:
            if hasattr(obj.organizer, 'organizer_profile') and obj.organizer.organizer_profile:
                if obj.organizer.organizer_profile.organization_name:
                    return obj.organizer.organizer_profile.organization_name
        except Exception:
            pass
        return getattr(obj.organizer, 'full_name', '') or "Nexus Productions"

    def get_time(self, obj):
        return obj.start_time.strftime('%I:%M %p') if obj.start_time else ''

    def get_dateFormatted(self, obj):
        return obj.date.strftime('%b %d, %Y') if obj.date else ''

    def get_startTime(self, obj):
        return obj.start_time.strftime('%H:%M') if obj.start_time else ''

    def get_endTime(self, obj):
        return obj.end_time.strftime('%H:%M') if obj.end_time else ''

    def get_startingPrice(self, obj):
        tiers = obj.tiers.all()
        if not tiers.exists():
            return '$0.00'
        min_price = min(t.price for t in tiers)
        return f"${min_price:,.2f}"

    def get_priceRange(self, obj):
        tiers = obj.tiers.all()
        if not tiers.exists():
            return 'Free'
        prices = [t.price for t in tiers]
        min_p, max_p = min(prices), max(prices)
        if min_p == max_p:
            return f"${min_p:,.2f}" if min_p > 0 else 'Free'
        return f"${min_p:,.0f} – ${max_p:,.0f}"

    def get_isBookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return SavedEvent.objects.filter(user=request.user, event=obj).exists()
        return False

    def get_likesCount(self, obj):
        return obj.likes.count()

    def get_isLiked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_commentsCount(self, obj):
        return obj.comments.filter(is_deleted=False).count()


class EventListSerializer(serializers.ModelSerializer):
    organizer = serializers.SerializerMethodField()
    venue = serializers.CharField(source='venue_name', read_only=True)
    venueName = serializers.CharField(source='venue_name', read_only=True)
    time = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    dateFormatted = serializers.SerializerMethodField()
    startTime = serializers.SerializerMethodField()
    endTime = serializers.SerializerMethodField()
    startingPrice = serializers.SerializerMethodField()
    spotsLeft = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    banner = serializers.SerializerMethodField()
    banner_image = serializers.SerializerMethodField()
    ticketsSold = serializers.SerializerMethodField()
    totalCapacity = serializers.SerializerMethodField()
    priceRange = serializers.SerializerMethodField()
    grossRevenue = serializers.SerializerMethodField()
    isBookmarked = serializers.SerializerMethodField()
    likesCount = serializers.SerializerMethodField()
    isLiked = serializers.SerializerMethodField()
    commentsCount = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    isEnded = serializers.SerializerMethodField()
    is_ended = serializers.SerializerMethodField()
    hasAssignedSeating = serializers.BooleanField(source='has_assigned_seating', read_only=True)
    passPlatformFeeToBuyer = serializers.BooleanField(source='pass_platform_fee_to_buyer', read_only=True)
    allowTicketTransfers = serializers.BooleanField(source='allow_ticket_transfers', read_only=True)
    requireAttendeePhone = serializers.BooleanField(source='require_attendee_phone', read_only=True)
    autoRefundCancelledEvents = serializers.BooleanField(source='auto_refund_cancelled_events', read_only=True)
    userRole = serializers.SerializerMethodField()
    staffPermissions = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            'id', 'title', 'organizer', 'category', 'date', 'dateFormatted',
            'time', 'start_time', 'startTime', 'end_time', 'endTime',
            'city', 'venue', 'venueName', 'venue_name', 'address', 'is_online',
            'startingPrice', 'spotsLeft', 'image', 'banner', 'banner_image',
            'status', 'isEnded', 'is_ended', 'ticketsSold', 'totalCapacity', 'priceRange',
            'grossRevenue', 'is_featured', 'isBookmarked', 'likesCount', 'isLiked', 'commentsCount',
            'has_assigned_seating', 'hasAssignedSeating',
            'pass_platform_fee_to_buyer', 'passPlatformFeeToBuyer',
            'allow_ticket_transfers', 'allowTicketTransfers',
            'require_attendee_phone', 'requireAttendeePhone',
            'auto_refund_cancelled_events', 'autoRefundCancelledEvents',
            'userRole', 'staffPermissions'
        )

    def get_status(self, obj):
        return obj.computed_status

    def get_isEnded(self, obj):
        return obj.is_ended

    def get_is_ended(self, obj):
        return obj.is_ended

    def get_image(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_banner(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_banner_image(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_organizer(self, obj):
        try:
            if hasattr(obj.organizer, 'organizer_profile') and obj.organizer.organizer_profile:
                if obj.organizer.organizer_profile.organization_name:
                    return obj.organizer.organizer_profile.organization_name
        except Exception:
            pass
        return getattr(obj.organizer, 'full_name', '') or "Nexus Productions"

    def get_time(self, obj):
        return obj.start_time.strftime('%I:%M %p') if obj.start_time else ''

    def get_date(self, obj):
        return str(obj.date) if obj.date else ''

    def get_dateFormatted(self, obj):
        return obj.date.strftime('%b %d, %Y') if obj.date else ''

    def get_startTime(self, obj):
        return obj.start_time.strftime('%H:%M') if obj.start_time else ''

    def get_endTime(self, obj):
        return obj.end_time.strftime('%H:%M') if obj.end_time else ''

    def get_startingPrice(self, obj):
        tiers = obj.tiers.all()
        if not tiers.exists():
            return 'Free'
        min_price = min(t.price for t in tiers)
        return f"${min_price:,.2f}" if min_price > 0 else 'Free Entry'

    def get_spotsLeft(self, obj):
        tiers = obj.tiers.all()
        total_capacity = sum(t.capacity for t in tiers)
        total_sold = sum(t.sold_count for t in tiers)
        return max(0, total_capacity - total_sold)

    def get_ticketsSold(self, obj):
        return sum(t.sold_count for t in obj.tiers.all())

    def get_totalCapacity(self, obj):
        return sum(t.capacity for t in obj.tiers.all())

    def get_priceRange(self, obj):
        tiers = obj.tiers.all()
        if not tiers.exists():
            return 'Free'
        prices = [t.price for t in tiers]
        min_p, max_p = min(prices), max(prices)
        if min_p == max_p:
            return f"${min_p:,.2f}" if min_p > 0 else 'Free'
        return f"${min_p:,.0f} – ${max_p:,.0f}"

    def get_grossRevenue(self, obj):
        tiers = obj.tiers.all()
        total = sum(t.price * t.sold_count for t in tiers)
        return f"${total:,.2f}"

    def get_isBookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return SavedEvent.objects.filter(user=request.user, event=obj).exists()
        return False

    def get_likesCount(self, obj):
        return obj.likes.count()

    def get_isLiked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_commentsCount(self, obj):
        return obj.comments.filter(is_deleted=False).count()

    def get_userRole(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if obj.organizer_id == request.user.id:
                return 'owner'
            from .models import EventStaff
            if EventStaff.objects.filter(event=obj, user=request.user).exists():
                return 'staff'
        return 'attendee'

    def get_staffPermissions(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if obj.organizer_id == request.user.id:
                return {'can_view_attendees': True, 'can_check_in': True, 'can_edit_attendees': True}
            from .models import EventStaff
            staff = EventStaff.objects.filter(event=obj, user=request.user).first()
            if staff:
                return {
                    'can_view_attendees': staff.can_view_attendees,
                    'can_check_in': staff.can_check_in,
                    'can_edit_attendees': staff.can_edit_attendees,
                }
        return None


class EventDetailSerializer(serializers.ModelSerializer):
    organizer = serializers.SerializerMethodField()
    venue = serializers.CharField(source='venue_name', read_only=True)
    venueName = serializers.CharField(source='venue_name', read_only=True)
    time = serializers.SerializerMethodField()
    dateFormatted = serializers.SerializerMethodField()
    startTime = serializers.SerializerMethodField()
    endTime = serializers.SerializerMethodField()
    startingPrice = serializers.SerializerMethodField()
    spotsLeft = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    banner = serializers.SerializerMethodField()
    banner_image = serializers.SerializerMethodField()
    ticketsSold = serializers.SerializerMethodField()
    totalCapacity = serializers.SerializerMethodField()
    grossRevenue = serializers.SerializerMethodField()
    tiers = TicketTierSerializer(many=True, read_only=True)
    isBookmarked = serializers.SerializerMethodField()
    likesCount = serializers.SerializerMethodField()
    isLiked = serializers.SerializerMethodField()
    commentsCount = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    isEnded = serializers.SerializerMethodField()
    is_ended = serializers.SerializerMethodField()
    hasAssignedSeating = serializers.BooleanField(source='has_assigned_seating', read_only=True)
    seatingLayout = serializers.JSONField(source='seating_layout', read_only=True)
    passPlatformFeeToBuyer = serializers.BooleanField(source='pass_platform_fee_to_buyer', read_only=True)
    allowTicketTransfers = serializers.BooleanField(source='allow_ticket_transfers', read_only=True)
    requireAttendeePhone = serializers.BooleanField(source='require_attendee_phone', read_only=True)
    autoRefundCancelledEvents = serializers.BooleanField(source='auto_refund_cancelled_events', read_only=True)
    userRole = serializers.SerializerMethodField()
    staffPermissions = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            'id', 'title', 'organizer', 'category', 'description', 'date', 'dateFormatted',
            'start_time', 'end_time', 'startTime', 'endTime', 'time',
            'venue_name', 'venueName', 'venue', 'city', 'address',
            'is_online', 'status', 'isEnded', 'is_ended', 'is_featured', 'image', 'banner', 'banner_image',
            'startingPrice', 'spotsLeft', 'ticketsSold', 'totalCapacity',
            'grossRevenue', 'tiers', 'isBookmarked', 'likesCount', 'isLiked', 'commentsCount',
            'has_assigned_seating', 'hasAssignedSeating', 'seating_layout', 'seatingLayout',
            'pass_platform_fee_to_buyer', 'passPlatformFeeToBuyer',
            'allow_ticket_transfers', 'allowTicketTransfers',
            'require_attendee_phone', 'requireAttendeePhone',
            'auto_refund_cancelled_events', 'autoRefundCancelledEvents',
            'userRole', 'staffPermissions'
        )

    def get_status(self, obj):
        return obj.computed_status

    def get_isEnded(self, obj):
        return obj.is_ended

    def get_is_ended(self, obj):
        return obj.is_ended

    def get_image(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_banner(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_banner_image(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_organizer(self, obj):
        try:
            if hasattr(obj.organizer, 'organizer_profile') and obj.organizer.organizer_profile:
                if obj.organizer.organizer_profile.organization_name:
                    return obj.organizer.organizer_profile.organization_name
        except Exception:
            pass
        return getattr(obj.organizer, 'full_name', '') or "Nexus Productions"

    def get_time(self, obj):
        return obj.start_time.strftime('%I:%M %p') if obj.start_time else ''

    def get_dateFormatted(self, obj):
        return obj.date.strftime('%b %d, %Y') if obj.date else ''

    def get_startTime(self, obj):
        return obj.start_time.strftime('%H:%M') if obj.start_time else ''

    def get_endTime(self, obj):
        return obj.end_time.strftime('%H:%M') if obj.end_time else ''

    def get_startingPrice(self, obj):
        tiers = obj.tiers.all()
        if not tiers.exists():
            return '$0.00'
        min_price = min(t.price for t in tiers)
        return f"${min_price:,.2f}"

    def get_spotsLeft(self, obj):
        tiers = obj.tiers.all()
        total_capacity = sum(t.capacity for t in tiers)
        total_sold = sum(t.sold_count for t in tiers)
        return max(0, total_capacity - total_sold)

    def get_ticketsSold(self, obj):
        return sum(t.sold_count for t in obj.tiers.all())

    def get_totalCapacity(self, obj):
        return sum(t.capacity for t in obj.tiers.all())

    def get_grossRevenue(self, obj):
        tiers = obj.tiers.all()
        total = sum(t.price * t.sold_count for t in tiers)
        return f"${total:,.2f}"

    def get_isBookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return SavedEvent.objects.filter(user=request.user, event=obj).exists()
        return False

    def get_likesCount(self, obj):
        return obj.likes.count()

    def get_isLiked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_commentsCount(self, obj):
        return obj.comments.filter(is_deleted=False).count()

    def get_userRole(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if obj.organizer_id == request.user.id:
                return 'owner'
            from .models import EventStaff
            if EventStaff.objects.filter(event=obj, user=request.user).exists():
                return 'staff'
        return 'attendee'

    def get_staffPermissions(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if obj.organizer_id == request.user.id:
                return {'can_view_attendees': True, 'can_check_in': True, 'can_edit_attendees': True}
            from .models import EventStaff
            staff = EventStaff.objects.filter(event=obj, user=request.user).first()
            if staff:
                return {
                    'can_view_attendees': staff.can_view_attendees,
                    'can_check_in': staff.can_check_in,
                    'can_edit_attendees': staff.can_edit_attendees,
                }
        return None


ManagerEventListSerializer = EventListSerializer
ManagerEventDetailSerializer = EventDetailSerializer


def _parse_tier_item(tier_dict):
    name = tier_dict.get('name') or tier_dict.get('tierName') or 'General Admission'
    raw_price = tier_dict.get('price', 0)
    try:
        price = Decimal(str(raw_price).replace('$', '').strip()) if raw_price not in [None, ''] else Decimal('0.00')
    except Exception:
        price = Decimal('0.00')
    raw_cap = tier_dict.get('capacity', 100)
    try:
        capacity = int(raw_cap) if raw_cap not in [None, ''] else 100
    except Exception:
        capacity = 100
    description = tier_dict.get('description', '') or ''
    return {
        'name': str(name).strip(),
        'price': max(Decimal('0.00'), price),
        'capacity': max(1, capacity),
        'description': str(description).strip(),
    }


class EventCreateUpdateSerializer(serializers.ModelSerializer):
    tiers = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)
    banner_image = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    seating_layout = serializers.JSONField(required=False)
    seatingLayout = serializers.JSONField(required=False)
    has_assigned_seating = serializers.BooleanField(required=False)
    hasAssignedSeating = serializers.BooleanField(required=False)
    assigned_staff_ids = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True)
    assignedStaffIds = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True)
    pass_platform_fee_to_buyer = serializers.BooleanField(required=False)
    passPlatformFeeToBuyer = serializers.BooleanField(required=False)
    allow_ticket_transfers = serializers.BooleanField(required=False)
    allowTicketTransfers = serializers.BooleanField(required=False)
    require_attendee_phone = serializers.BooleanField(required=False)
    requireAttendeePhone = serializers.BooleanField(required=False)
    auto_refund_cancelled_events = serializers.BooleanField(required=False)
    autoRefundCancelledEvents = serializers.BooleanField(required=False)

    class Meta:
        model = Event
        fields = (
            'id', 'title', 'category', 'description', 'banner_image',
            'date', 'start_time', 'end_time', 'venue_name', 'city',
            'address', 'is_online', 'status', 'tiers',
            'has_assigned_seating', 'hasAssignedSeating', 'seating_layout', 'seatingLayout',
            'assigned_staff_ids', 'assignedStaffIds',
            'pass_platform_fee_to_buyer', 'passPlatformFeeToBuyer',
            'allow_ticket_transfers', 'allowTicketTransfers',
            'require_attendee_phone', 'requireAttendeePhone',
            'auto_refund_cancelled_events', 'autoRefundCancelledEvents',
        )

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        if 'venueName' in data:
            data['venue_name'] = data.pop('venueName')
        if 'startTime' in data:
            data['start_time'] = data.pop('startTime')
        if 'endTime' in data:
            data['end_time'] = data.pop('endTime')
        if 'banner' in data:
            data['banner_image'] = data.pop('banner')
        if 'isOnline' in data:
            data['is_online'] = data.pop('isOnline')
        if 'seatingLayout' in data:
            data['seating_layout'] = data.pop('seatingLayout')
        if 'hasAssignedSeating' in data:
            data['has_assigned_seating'] = data.pop('hasAssignedSeating')

        if 'passPlatformFeeToBuyer' in data:
            data['pass_platform_fee_to_buyer'] = data.pop('passPlatformFeeToBuyer')
        if 'allowTicketTransfers' in data:
            data['allow_ticket_transfers'] = data.pop('allowTicketTransfers')
        if 'requireAttendeePhone' in data:
            data['require_attendee_phone'] = data.pop('requireAttendeePhone')
        if 'autoRefundCancelledEvents' in data:
            data['auto_refund_cancelled_events'] = data.pop('autoRefundCancelledEvents')

        # Parse stringified JSON fields if submitted via multipart/form-data
        if 'tiers' in data and isinstance(data['tiers'], str):
            try:
                data['tiers'] = json.loads(data['tiers'])
            except Exception:
                pass

        if 'seating_layout' in data and isinstance(data['seating_layout'], str):
            try:
                data['seating_layout'] = json.loads(data['seating_layout'])
            except Exception:
                pass

        raw_staff_ids = data.pop('assignedStaffIds', None)
        if raw_staff_ids is None:
            raw_staff_ids = data.pop('assigned_staff_ids', None)

        if raw_staff_ids is not None:
            if isinstance(raw_staff_ids, str):
                try:
                    raw_staff_ids = json.loads(raw_staff_ids)
                except Exception:
                    pass

            clean_staff_ids = []
            if isinstance(raw_staff_ids, (list, tuple, set)):
                for item in raw_staff_ids:
                    if item is None:
                        continue
                    if isinstance(item, int):
                        clean_staff_ids.append(item)
                    elif isinstance(item, str) and item.strip().isdigit():
                        clean_staff_ids.append(int(item.strip()))
                    elif isinstance(item, dict):
                        uid = item.get('userId') or item.get('user_id') or item.get('user') or item.get('id')
                        if uid is not None and str(uid).strip().isdigit():
                            clean_staff_ids.append(int(str(uid).strip()))
            data['assigned_staff_ids'] = clean_staff_ids

        if data.get('end_time') in ['', None]:
            data['end_time'] = None

        banner_val = data.get('banner_image')
        if banner_val in ['', None]:
            if self.instance and 'banner_image' not in data:
                pass
            else:
                data['banner_image'] = None
        elif hasattr(banner_val, 'read'):
            # Direct file upload (via FormData or file stream)
            uploaded_url = upload_image_to_cloudinary(banner_val, folder='evento/banners')
            data['banner_image'] = uploaded_url
        elif isinstance(banner_val, str) and banner_val.startswith(('http://', 'https://')):
            # Direct Cloudinary / external HTTPS URL
            if self.instance and banner_val == resolve_image_url(self.instance.banner_image):
                data.pop('banner_image', None)
            else:
                data['banner_image'] = banner_val
        elif isinstance(banner_val, str) and (banner_val.startswith('/media/') or banner_val.startswith('events/')):
            data.pop('banner_image', None)

        if data.get('venue_name') is None:
            data['venue_name'] = ''
        if data.get('address') is None:
            data['address'] = ''
        return super().to_internal_value(data)

    def validate(self, attrs):
        start_time = attrs.get('start_time') or getattr(self.instance, 'start_time', None)
        end_time = attrs.get('end_time') if 'end_time' in attrs else getattr(self.instance, 'end_time', None)
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError({'endTime': 'End time must be later than start time.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        tiers_data = validated_data.pop('tiers', [])
        seating_layout = validated_data.pop('seating_layout', None)
        assigned_staff_ids = validated_data.pop('assigned_staff_ids', None)

        # Inherit organizer studio defaults if not explicitly provided in creation payload
        organizer = validated_data.get('organizer')
        if not organizer and self.context.get('request'):
            organizer = self.context['request'].user
        if organizer and hasattr(organizer, 'organizer_profile') and organizer.organizer_profile:
            profile = organizer.organizer_profile
            if 'pass_platform_fee_to_buyer' not in validated_data:
                validated_data['pass_platform_fee_to_buyer'] = profile.pass_platform_fee_to_buyer
            if 'allow_ticket_transfers' not in validated_data:
                validated_data['allow_ticket_transfers'] = profile.allow_ticket_transfers
            if 'require_attendee_phone' not in validated_data:
                validated_data['require_attendee_phone'] = profile.require_attendee_phone
            if 'auto_refund_cancelled_events' not in validated_data:
                validated_data['auto_refund_cancelled_events'] = profile.auto_refund_cancelled_events

        event = Event.objects.create(**validated_data)

        if seating_layout:
            sync_seating_layout_to_db(event, seating_layout)
        elif tiers_data:
            for tier_dict in tiers_data:
                parsed = _parse_tier_item(tier_dict)
                TicketTier.objects.create(event=event, **parsed)
        else:
            TicketTier.objects.create(event=event, name='General Admission', price=Decimal('0.00'), capacity=100)

        if assigned_staff_ids is not None:
            _sync_event_staff_ids(event, assigned_staff_ids)

        return event

    @transaction.atomic
    def update(self, instance, validated_data):
        tiers_data = validated_data.pop('tiers', None)
        seating_layout = validated_data.pop('seating_layout', None)
        assigned_staff_ids = validated_data.pop('assigned_staff_ids', None)

        # Ticketing policies are locked at creation to protect buyer terms, fee consistency, and accounting ledgers
        validated_data.pop('pass_platform_fee_to_buyer', None)
        validated_data.pop('allow_ticket_transfers', None)
        validated_data.pop('require_attendee_phone', None)
        validated_data.pop('auto_refund_cancelled_events', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if seating_layout is not None:
            sync_seating_layout_to_db(instance, seating_layout)
        elif tiers_data is not None:
            existing_tiers = {t.id: t for t in instance.tiers.all()}
            processed_tier_ids = set()

            for tier_dict in tiers_data:
                raw_tier_id = tier_dict.get('id') or tier_dict.get('tier_id') or tier_dict.get('tierId')
                tier_id = int(raw_tier_id) if raw_tier_id and str(raw_tier_id).isdigit() else None
                parsed = _parse_tier_item(tier_dict)

                if tier_id and tier_id in existing_tiers:
                    existing_tier = existing_tiers[tier_id]
                    if parsed['capacity'] < existing_tier.sold_count:
                        raise serializers.ValidationError(
                            f"Capacity for '{existing_tier.name}' cannot be less than tickets already sold ({existing_tier.sold_count})."
                        )
                    existing_tier.name = parsed['name']
                    existing_tier.price = parsed['price']
                    existing_tier.capacity = parsed['capacity']
                    existing_tier.description = parsed['description']
                    existing_tier.save()
                    processed_tier_ids.add(tier_id)
                else:
                    new_tier = TicketTier.objects.create(event=instance, **parsed)
                    processed_tier_ids.add(new_tier.id)

            for existing_id, existing_tier in existing_tiers.items():
                if existing_id not in processed_tier_ids:
                    if existing_tier.sold_count > 0:
                        raise serializers.ValidationError(
                            f"Cannot delete tier '{existing_tier.name}' because {existing_tier.sold_count} ticket(s) have already been sold."
                        )
                    existing_tier.delete()

        if assigned_staff_ids is not None:
            _sync_event_staff_ids(instance, assigned_staff_ids)

        return instance





class StaffUserSearchSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    fullName = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    role = serializers.CharField(read_only=True)

    def get_fullName(self, obj):
        name = getattr(obj, 'full_name', '') or ''
        return name.strip() if name.strip() else obj.email.split('@')[0]

    def get_full_name(self, obj):
        return self.get_fullName(obj)

    def get_username(self, obj):
        return obj.email.split('@')[0]


class EventStaffSerializer(serializers.ModelSerializer):
    userId = serializers.IntegerField(source='user.id', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    fullName = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    roleTitle = serializers.CharField(source='role_title', required=False)
    role = serializers.CharField(source='role_title', read_only=True)
    canViewAttendees = serializers.BooleanField(source='can_view_attendees')
    canCheckIn = serializers.BooleanField(source='can_check_in')
    canEditAttendees = serializers.BooleanField(source='can_edit_attendees')
    assignedAt = serializers.DateTimeField(source='assigned_at', read_only=True)

    class Meta:
        from .models import EventStaff
        model = EventStaff
        fields = (
            'id', 'userId', 'user_id', 'user', 'email', 'fullName', 'full_name', 'username',
            'role_title', 'roleTitle', 'role',
            'can_view_attendees', 'canViewAttendees',
            'can_check_in', 'canCheckIn',
            'can_edit_attendees', 'canEditAttendees',
            'assigned_at', 'assignedAt'
        )

    def get_fullName(self, obj):
        name = getattr(obj.user, 'full_name', '') or ''
        return name.strip() if name.strip() else obj.user.email.split('@')[0]

    def get_full_name(self, obj):
        return self.get_fullName(obj)

    def get_username(self, obj):
        return obj.user.email.split('@')[0]


class AddEventStaffSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    userId = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
    roleTitle = serializers.CharField(max_length=100, required=False, default='Stage Coordinator')
    role_title = serializers.CharField(max_length=100, required=False)
    canViewAttendees = serializers.BooleanField(default=True, required=False)
    can_view_attendees = serializers.BooleanField(default=True, required=False)
    canCheckIn = serializers.BooleanField(default=True, required=False)
    can_check_in = serializers.BooleanField(default=True, required=False)
    canEditAttendees = serializers.BooleanField(default=False, required=False)
    can_edit_attendees = serializers.BooleanField(default=False, required=False)
    saveToStudioTeam = serializers.BooleanField(default=False, required=False)
    save_to_studio_team = serializers.BooleanField(default=False, required=False)

    def validate(self, attrs):
        from django.contrib.auth import get_user_model
        from .models import EventStaff
        User = get_user_model()
        event = self.context.get('event')

        user_id = attrs.get('userId') or attrs.get('user_id')
        email = (attrs.get('email') or '').lower().strip()

        target_user = None
        if user_id:
            target_user = User.objects.filter(pk=user_id, is_active=True).first()
        elif email:
            target_user = User.objects.filter(email__iexact=email, is_active=True).first()

        if not target_user:
            raise serializers.ValidationError({'detail': 'No active registered user found with the provided email or ID.'})

        # Ensure target user has a manager account
        is_manager = bool(
            getattr(target_user, 'is_organizer', False) or
            getattr(target_user, 'role', '') == 'manager' or
            hasattr(target_user, 'organizer_profile')
        )
        if not is_manager:
            raise serializers.ValidationError({'detail': 'Only users with a registered manager account can be assigned as event staff.'})

        if event and target_user == event.organizer:
            raise serializers.ValidationError({'detail': 'Event organizer already has full management access to this event.'})

        if event and EventStaff.objects.filter(event=event, user=target_user).exists():
            raise serializers.ValidationError({'detail': f"'{target_user.email}' is already assigned as staff for this event."})

        attrs['target_user'] = target_user
        return attrs

    def create(self, validated_data):
        from .models import EventStaff
        from accounts.models import StudioStaffMember
        event = self.context['event']
        target_user = validated_data['target_user']

        role_title = (
            validated_data.get('role_title')
            if 'role_title' in validated_data
            else validated_data.get('roleTitle', 'Stage Coordinator')
        )
        can_view = (
            validated_data.get('can_view_attendees')
            if 'can_view_attendees' in validated_data
            else validated_data.get('canViewAttendees', True)
        )
        can_check = (
            validated_data.get('can_check_in')
            if 'can_check_in' in validated_data
            else validated_data.get('canCheckIn', True)
        )
        can_edit = (
            validated_data.get('can_edit_attendees')
            if 'can_edit_attendees' in validated_data
            else validated_data.get('canEditAttendees', False)
        )

        staff_record = EventStaff.objects.create(
            event=event,
            user=target_user,
            role_title=role_title,
            can_view_attendees=can_view,
            can_check_in=can_check,
            can_edit_attendees=can_edit
        )

        # Optionally save to studio roster
        save_to_studio = (
            validated_data.get('save_to_studio_team')
            if 'save_to_studio_team' in validated_data
            else validated_data.get('saveToStudioTeam', False)
        )
        if save_to_studio and event.organizer:
            StudioStaffMember.objects.update_or_create(
                organizer=event.organizer,
                user=target_user,
                defaults={
                    'role_title': role_title,
                    'default_can_view_attendees': can_view,
                    'default_can_check_in': can_check,
                    'default_can_edit_attendees': can_edit,
                }
            )

        return staff_record


class BulkAssignEventStaffSerializer(serializers.Serializer):
    staffUserIds = serializers.ListField(child=serializers.IntegerField(), required=False)
    staff_user_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    staffMembers = serializers.ListField(child=serializers.DictField(), required=False)
    staff_members = serializers.ListField(child=serializers.DictField(), required=False)

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        raw_ids = data.get('staffUserIds') if 'staffUserIds' in data else data.get('staff_user_ids')
        if raw_ids is not None and isinstance(raw_ids, (list, tuple, set)):
            clean_ids = []
            for item in raw_ids:
                if item is None:
                    continue
                if isinstance(item, int):
                    clean_ids.append(item)
                elif isinstance(item, str) and item.strip().isdigit():
                    clean_ids.append(int(item.strip()))
                elif isinstance(item, dict):
                    uid = item.get('userId') or item.get('user_id') or item.get('user') or item.get('id')
                    if uid is not None and str(uid).strip().isdigit():
                        clean_ids.append(int(str(uid).strip()))
            data['staff_user_ids'] = clean_ids
            data.pop('staffUserIds', None)
        return super().to_internal_value(data)

    def create(self, validated_data):
        from .models import EventStaff
        from accounts.models import StudioStaffMember, User
        event = self.context['event']

        user_ids = (
            validated_data.get('staff_user_ids')
            if 'staff_user_ids' in validated_data
            else validated_data.get('staffUserIds', [])
        )
        members_list = (
            validated_data.get('staff_members')
            if 'staff_members' in validated_data
            else validated_data.get('staffMembers', [])
        )

        assigned_records = []

        # 1. Handle members list with custom permissions
        if members_list:
            for m in members_list:
                uid = m.get('userId') or m.get('user_id') or m.get('id')
                if not uid or uid == event.organizer_id:
                    continue
                user_obj = User.objects.filter(pk=uid, is_active=True).first()
                if not user_obj:
                    continue
                role_title = m.get('roleTitle') or m.get('role_title') or m.get('role') or 'Stage Coordinator'
                can_view = m.get('canViewAttendees', m.get('can_view_attendees', True))
                can_check = m.get('canCheckIn', m.get('can_check_in', True))
                can_edit = m.get('canEditAttendees', m.get('can_edit_attendees', False))

                record, _ = EventStaff.objects.update_or_create(
                    event=event,
                    user=user_obj,
                    defaults={
                        'role_title': role_title,
                        'can_view_attendees': can_view,
                        'can_check_in': can_check,
                        'can_edit_attendees': can_edit,
                    }
                )
                assigned_records.append(record)

        # 2. Handle simple user IDs array
        elif user_ids:
            studio_map = {
                sm.user_id: sm
                for sm in StudioStaffMember.objects.filter(organizer=event.organizer, user_id__in=user_ids)
            }
            for uid in user_ids:
                if uid == event.organizer_id:
                    continue
                user_obj = User.objects.filter(pk=uid, is_active=True).first()
                if not user_obj:
                    continue
                studio_member = studio_map.get(uid)
                role_title = studio_member.role_title if studio_member else 'Stage Coordinator'
                can_view = studio_member.default_can_view_attendees if studio_member else True
                can_check = studio_member.default_can_check_in if studio_member else True
                can_edit = studio_member.default_can_edit_attendees if studio_member else False

                record, _ = EventStaff.objects.update_or_create(
                    event=event,
                    user=user_obj,
                    defaults={
                        'role_title': role_title,
                        'can_view_attendees': can_view,
                        'can_check_in': can_check,
                        'can_edit_attendees': can_edit,
                    }
                )
                assigned_records.append(record)

        return assigned_records



class StaffAssignedEventSerializer(serializers.ModelSerializer):
    organizer = serializers.SerializerMethodField()
    venue = serializers.CharField(source='venue_name', read_only=True)
    venueName = serializers.CharField(source='venue_name', read_only=True)
    time = serializers.SerializerMethodField()
    dateFormatted = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    totalAttendees = serializers.SerializerMethodField()
    checkedInCount = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            'id', 'title', 'organizer', 'category', 'date', 'dateFormatted',
            'time', 'venue', 'venueName', 'city', 'address', 'is_online',
            'image', 'status', 'permissions', 'totalAttendees', 'checkedInCount'
        )

    def get_organizer(self, obj):
        try:
            if hasattr(obj.organizer, 'organizer_profile') and obj.organizer.organizer_profile:
                if obj.organizer.organizer_profile.organization_name:
                    return obj.organizer.organizer_profile.organization_name
        except Exception:
            pass
        return getattr(obj.organizer, 'full_name', '') or "Event Host"

    def get_image(self, obj):
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_time(self, obj):
        return obj.start_time.strftime('%I:%M %p') if obj.start_time else ''

    def get_dateFormatted(self, obj):
        return obj.date.strftime('%b %d, %Y') if obj.date else ''

    def get_permissions(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return {}
        from .models import EventStaff
        staff = EventStaff.objects.filter(event=obj, user=request.user).first()
        if not staff:
            if obj.organizer == request.user:
                return {'can_view_attendees': True, 'can_check_in': True, 'can_edit_attendees': True}
            return {}
        return {
            'can_view_attendees': staff.can_view_attendees,
            'can_check_in': staff.can_check_in,
            'can_edit_attendees': staff.can_edit_attendees,
        }

    def get_totalAttendees(self, obj):
        return obj.attendees.count()

    def get_checkedInCount(self, obj):
        return obj.attendees.filter(is_checked_in=True).count()


# ==========================================
# SOCIAL COMMENTS & REPLIES SERIALIZERS
# ==========================================

class CommentUserSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source='full_name', read_only=True)
    isOrganizer = serializers.BooleanField(source='is_organizer', read_only=True)
    avatarUrl = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        from django.contrib.auth import get_user_model
        model = get_user_model()
        fields = ('id', 'email', 'username', 'fullName', 'full_name', 'avatarUrl', 'avatar_url', 'bio', 'role', 'isOrganizer')

    def _resolve_avatar(self, obj):
        url = getattr(obj, 'avatar_url', '') or ''
        if not url:
            return ''
        if url.startswith(('http://', 'https://')):
            return url
        request = self.context.get('request')
        if url.startswith('/media/'):
            if request:
                return request.build_absolute_uri(url)
            return f"http://127.0.0.1:8000{url}"
        return url

    def get_avatarUrl(self, obj):
        return self._resolve_avatar(obj)

    def get_avatar_url(self, obj):
        return self._resolve_avatar(obj)


class CommentSerializer(serializers.ModelSerializer):
    eventId = serializers.IntegerField(source='event_id', read_only=True)
    parentId = serializers.IntegerField(source='parent_id', read_only=True)
    user = CommentUserSerializer(read_only=True)
    authorName = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    rawContent = serializers.CharField(source='content', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    createdAtFormatted = serializers.SerializerMethodField()
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    isDeleted = serializers.BooleanField(source='is_deleted', read_only=True)
    isOwner = serializers.SerializerMethodField()
    canDelete = serializers.SerializerMethodField()
    canEdit = serializers.SerializerMethodField()
    likeCount = serializers.SerializerMethodField()
    isLiked = serializers.SerializerMethodField()
    repliesCount = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = EventComment
        fields = (
            'id', 'eventId', 'parentId', 'user', 'authorName', 'content', 'rawContent',
            'createdAt', 'createdAtFormatted', 'updatedAt', 'isDeleted', 'isOwner',
            'canDelete', 'canEdit', 'likeCount', 'isLiked', 'repliesCount', 'replies'
        )

    def get_authorName(self, obj):
        return obj.user.full_name or obj.user.email.split('@')[0]

    def get_content(self, obj):
        if obj.is_deleted:
            return "[This comment was deleted by user]"
        return obj.content

    def get_createdAtFormatted(self, obj):
        return format_relative_time(obj.created_at)

    def get_isOwner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user_id == request.user.id
        return False

    def get_canEdit(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and not obj.is_deleted:
            return obj.user_id == request.user.id
        return False

    def get_canDelete(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and not obj.is_deleted:
            return (obj.user_id == request.user.id) or (obj.event.organizer_id == request.user.id)
        return False

    def get_likeCount(self, obj):
        return obj.likes.count()

    def get_isLiked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_repliesCount(self, obj):
        return obj.replies.filter(is_deleted=False).count()

    def get_replies(self, obj):
        # Return immediate child replies if this is a top-level comment and include_replies context is True
        if obj.parent_id is None and self.context.get('include_replies', True):
            replies_qs = obj.replies.all().select_related('user').prefetch_related('likes').order_by('created_at')
            return CommentSerializer(replies_qs, many=True, context={**self.context, 'include_replies': False}).data
        return []


class CommentCreateSerializer(serializers.ModelSerializer):
    parentId = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = EventComment
        fields = ('content', 'parentId')

    def validate_content(self, value):
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("Comment cannot be blank.")
        if len(stripped) > 1000:
            raise serializers.ValidationError("Comment cannot exceed 1000 characters.")
        return stripped

    def validate_parentId(self, value):
        if value:
            event = self.context.get('event')
            parent = EventComment.objects.filter(id=value).first()
            if not parent:
                raise serializers.ValidationError("Parent comment does not exist.")
            if event and parent.event_id != event.id:
                raise serializers.ValidationError("Parent comment does not belong to this event.")
        return value


