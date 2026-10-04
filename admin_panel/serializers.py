from rest_framework import serializers
from django.utils import timezone
from .models import HomepageBanner, RecommendedEvent, AuditLog, PlatformReport, PlatformSetting
from accounts.models import User, OrganizerProfile, SettlementAccount
from events.models import Event, TicketTier
from events.utils.media_utils import resolve_image_url
from tickets.models import Order, AttendeeTicket
from payouts.models import Payout


class HomepageBannerSerializer(serializers.ModelSerializer):
    eventTitle = serializers.SerializerMethodField()
    isCurrentlyActive = serializers.BooleanField(source='is_currently_active', read_only=True)
    activeFrom = serializers.DateTimeField(source='active_from', required=False, allow_null=True)
    activeUntil = serializers.DateTimeField(source='active_until', required=False, allow_null=True)
    displayOrder = serializers.IntegerField(source='display_order', required=False, default=1)
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    imageUrl = serializers.CharField(source='image_url')
    ctaText = serializers.CharField(source='cta_text', required=False, default='Get Tickets')
    customUrl = serializers.CharField(source='custom_url', required=False, allow_blank=True, default='')
    eventId = serializers.PrimaryKeyRelatedField(
        source='event',
        queryset=Event.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = HomepageBanner
        fields = (
            'id', 'title', 'subtitle', 'imageUrl', 'eventId', 'eventTitle',
            'ctaText', 'customUrl', 'displayOrder', 'isActive', 'isCurrentlyActive',
            'activeFrom', 'activeUntil', 'created_at', 'updated_at'
        )

    def get_eventTitle(self, obj):
        return obj.event.title if obj.event else None


class RecommendedEventSerializer(serializers.ModelSerializer):
    eventTitle = serializers.CharField(source='event.title', read_only=True)
    eventCategory = serializers.CharField(source='event.category', read_only=True)
    eventCity = serializers.CharField(source='event.city', read_only=True)
    eventDate = serializers.DateField(source='event.date', read_only=True)
    eventBanner = serializers.CharField(source='event.banner_url', read_only=True)
    eventStatus = serializers.CharField(source='event.status', read_only=True)
    organizerName = serializers.SerializerMethodField()
    priorityRank = serializers.IntegerField(source='priority_rank', required=False, default=1)
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    isCurrentlyActive = serializers.BooleanField(source='is_currently_active', read_only=True)
    startDate = serializers.DateTimeField(source='start_date', required=False, allow_null=True)
    endDate = serializers.DateTimeField(source='end_date', required=False, allow_null=True)
    eventId = serializers.PrimaryKeyRelatedField(
        source='event',
        queryset=Event.objects.all()
    )

    class Meta:
        model = RecommendedEvent
        fields = (
            'id', 'eventId', 'eventTitle', 'eventCategory', 'eventCity', 'eventDate',
            'eventBanner', 'eventStatus', 'organizerName', 'priorityRank',
            'isActive', 'isCurrentlyActive', 'startDate', 'endDate', 'created_at'
        )

    def get_organizerName(self, obj):
        if obj.event and obj.event.organizer:
            prof = getattr(obj.event.organizer, 'organizer_profile', None)
            return prof.organization_name if prof else (obj.event.organizer.full_name or obj.event.organizer.email)
        return 'Unknown'


class AuditLogSerializer(serializers.ModelSerializer):
    actorEmail = serializers.SerializerMethodField()
    actorName = serializers.SerializerMethodField()
    actionType = serializers.CharField(source='action_type')
    targetModel = serializers.CharField(source='target_model')
    targetId = serializers.CharField(source='target_id')
    changesPayload = serializers.JSONField(source='changes_payload')
    ipAddress = serializers.CharField(source='ip_address')
    createdAt = serializers.DateTimeField(source='created_at')

    class Meta:
        model = AuditLog
        fields = (
            'id', 'actorEmail', 'actorName', 'actionType', 'targetModel',
            'targetId', 'description', 'changesPayload', 'ipAddress', 'createdAt'
        )

    def get_actorEmail(self, obj):
        return obj.actor.email if obj.actor else 'System Automated'

    def get_actorName(self, obj):
        return obj.actor.full_name if (obj.actor and obj.actor.full_name) else (obj.actor.email if obj.actor else 'System')


class PlatformReportSerializer(serializers.ModelSerializer):
    reporterEmail = serializers.SerializerMethodField()
    reporterName = serializers.SerializerMethodField()
    reporterRole = serializers.SerializerMethodField()
    resolvedByEmail = serializers.SerializerMethodField()
    reportType = serializers.CharField(source='report_type', required=False, default='support')
    targetModel = serializers.CharField(source='target_model', required=False, default='Platform')
    targetId = serializers.CharField(source='target_id', required=False, allow_blank=True, default='')
    resolutionNotes = serializers.CharField(source='resolution_notes', required=False, allow_blank=True)
    resolvedAt = serializers.DateTimeField(source='resolved_at', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = PlatformReport
        fields = (
            'id', 'reporterEmail', 'reporterName', 'reporterRole', 'reportType',
            'targetModel', 'targetId', 'reason', 'details', 'status',
            'resolvedByEmail', 'resolutionNotes', 'resolvedAt', 'createdAt'
        )

    def get_reporterEmail(self, obj):
        return obj.reporter.email if obj.reporter else 'Anonymous'

    def get_reporterName(self, obj):
        if not obj.reporter:
            return 'Anonymous'
        return getattr(obj.reporter, 'full_name', '') or getattr(obj.reporter, 'username', '') or obj.reporter.email

    def get_reporterRole(self, obj):
        if not obj.reporter:
            return 'Guest'
        if obj.reporter.is_superuser or obj.reporter.is_staff:
            return 'Super Admin'
        if hasattr(obj.reporter, 'organizer_profile'):
            return 'Organizer'
        return 'Attendee'

    def get_resolvedByEmail(self, obj):
        return obj.resolved_by.email if obj.resolved_by else None


class PlatformSettingSerializer(serializers.ModelSerializer):
    dataType = serializers.CharField(source='data_type')
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = PlatformSetting
        fields = ('key', 'value', 'dataType', 'description', 'updatedAt')


class AdminUserListSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source='full_name', read_only=True)
    isOrganizer = serializers.BooleanField(source='is_organizer', read_only=True)
    isSuperAdmin = serializers.BooleanField(source='is_super_admin', read_only=True)
    isSuspended = serializers.BooleanField(source='is_suspended', read_only=True)
    suspensionReason = serializers.CharField(source='suspension_reason', read_only=True)
    organizationName = serializers.SerializerMethodField()
    totalOrders = serializers.SerializerMethodField()
    totalSpent = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'fullName', 'phone', 'city',
            'role', 'is_active', 'isSuspended', 'suspensionReason',
            'isOrganizer', 'isSuperAdmin', 'organizationName',
            'totalOrders', 'totalSpent', 'createdAt'
        )

    def get_organizationName(self, obj):
        prof = getattr(obj, 'organizer_profile', None)
        return prof.organization_name if prof else ''

    def get_totalOrders(self, obj):
        return obj.orders.filter(status__in=['Confirmed', 'Paid', 'Completed']).count()

    def get_totalSpent(self, obj):
        from django.db.models import Sum
        total = obj.orders.filter(status__in=['Confirmed', 'Paid', 'Completed']).aggregate(s=Sum('total_amount'))['s']
        return f"${float(total):,.2f}" if total else "$0.00"


class AdminOrganizerSerializer(serializers.ModelSerializer):
    userId = serializers.IntegerField(source='user.id', read_only=True)
    userEmail = serializers.CharField(source='user.email', read_only=True)
    ownerName = serializers.CharField(source='user.full_name', read_only=True)
    isSuspended = serializers.BooleanField(source='user.is_suspended', read_only=True)
    organizationName = serializers.CharField(source='organization_name')
    supportEmail = serializers.CharField(source='support_email')
    supportPhone = serializers.CharField(source='support_phone')
    totalEvents = serializers.SerializerMethodField()
    totalGross = serializers.SerializerMethodField()
    availableBalance = serializers.SerializerMethodField()
    disbursedTotal = serializers.SerializerMethodField()
    primarySettlement = serializers.SerializerMethodField()

    class Meta:
        model = OrganizerProfile
        fields = (
            'id', 'userId', 'userEmail', 'ownerName', 'organizationName',
            'handle', 'supportEmail', 'supportPhone', 'website', 'instagram',
            'bio', 'logo_url', 'isSuspended', 'totalEvents', 'totalGross',
            'availableBalance', 'disbursedTotal', 'primarySettlement'
        )

    def get_totalEvents(self, obj):
        return Event.objects.filter(organizer=obj.user).count()

    def get_totalGross(self, obj):
        from payouts.views import calculate_organizer_financials
        fin = calculate_organizer_financials(obj.user)
        return f"${float(fin['gross_ticket_sales']):,.2f}"

    def get_availableBalance(self, obj):
        from payouts.views import calculate_organizer_financials
        fin = calculate_organizer_financials(obj.user)
        return f"${float(fin['available_balance']):,.2f}"

    def get_disbursedTotal(self, obj):
        from payouts.views import calculate_organizer_financials
        fin = calculate_organizer_financials(obj.user)
        return f"${float(fin['disbursed_total']):,.2f}"

    def get_primarySettlement(self, obj):
        acc = SettlementAccount.objects.filter(organizer=obj.user, is_primary=True).first()
        if acc:
            return f"{acc.method_type.upper()}: {acc.paypal_email or acc.account_number}"
        return 'None Configured'


class AdminEventListSerializer(serializers.ModelSerializer):
    organizerName = serializers.SerializerMethodField()
    organizerEmail = serializers.CharField(source='organizer.email', read_only=True)
    ticketsSold = serializers.SerializerMethodField()
    totalCapacity = serializers.SerializerMethodField()
    grossRevenue = serializers.SerializerMethodField()
    checkedInCount = serializers.SerializerMethodField()
    isFeatured = serializers.BooleanField(source='is_featured', read_only=True)
    banner_url = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            'id', 'title', 'category', 'status', 'date', 'start_time', 'end_time',
            'venue_name', 'city', 'banner_url', 'is_online', 'isFeatured',
            'organizerName', 'organizerEmail', 'ticketsSold', 'totalCapacity',
            'grossRevenue', 'checkedInCount', 'created_at'
        )

    def get_banner_url(self, obj):
        if not obj.banner_image:
            return None
        return resolve_image_url(obj.banner_image, self.context.get('request'))

    def get_organizerName(self, obj):
        prof = getattr(obj.organizer, 'organizer_profile', None)
        return prof.organization_name if prof else (obj.organizer.full_name or obj.organizer.email)

    def get_ticketsSold(self, obj):
        if obj.has_assigned_seating and obj.seats.exists():
            return obj.seats.filter(status='booked').count()
        return sum(t.sold_count for t in obj.tiers.all())

    def get_totalCapacity(self, obj):
        if obj.has_assigned_seating and obj.seats.exists():
            return obj.seats.count()
        return sum(t.capacity for t in obj.tiers.all())

    def get_grossRevenue(self, obj):
        rev = sum(t.price * t.sold_count for t in obj.tiers.all())
        return f"${float(rev):,.2f}"

    def get_checkedInCount(self, obj):
        if hasattr(obj, 'annotated_checked_in'):
            return obj.annotated_checked_in
        return AttendeeTicket.objects.filter(event=obj, is_checked_in=True).count()


class AdminTransactionSerializer(serializers.ModelSerializer):
    buyerName = serializers.SerializerMethodField()
    buyerEmail = serializers.CharField(source='user.email', read_only=True)
    eventTitle = serializers.CharField(source='event.title', read_only=True)
    organizerName = serializers.SerializerMethodField()
    tierName = serializers.CharField(source='tier.name', read_only=True)
    totalAmount = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2, read_only=True)
    platformFee = serializers.DecimalField(source='fees', max_digits=10, decimal_places=2, read_only=True)
    paypalCaptureId = serializers.CharField(source='paypal_capture_id', read_only=True)
    paypalOrderId = serializers.CharField(source='paypal_order_id', read_only=True)
    orderNumber = serializers.CharField(source='order_number', read_only=True)
    paymentMethod = serializers.CharField(source='payment_method', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'orderNumber', 'buyerName', 'buyerEmail', 'eventTitle',
            'organizerName', 'tierName', 'quantity', 'unit_price',
            'totalAmount', 'platformFee', 'paymentMethod', 'status',
            'paypalOrderId', 'paypalCaptureId', 'createdAt'
        )

    def get_buyerName(self, obj):
        return obj.user.full_name or obj.user.email

    def get_organizerName(self, obj):
        prof = getattr(obj.event.organizer, 'organizer_profile', None)
        return prof.organization_name if prof else (obj.event.organizer.full_name or obj.event.organizer.email)


class AdminPayoutSerializer(serializers.ModelSerializer):
    organizer_name = serializers.SerializerMethodField()
    organizer_email = serializers.CharField(source='organizer.email', read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    destination_summary = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = (
            'id', 'payout_number', 'organizer', 'organizer_name', 'organizer_email',
            'settlement_account', 'method_type', 'destination_summary',
            'gross_amount', 'fee_deducted', 'net_disbursed', 'paypal_batch_id',
            'paypal_payout_item_id', 'utr_reference', 'status', 'failure_reason',
            'created_at'
        )

    def get_organizer_name(self, obj):
        if not obj.organizer:
            return 'Unknown Organizer'
        prof = getattr(obj.organizer, 'organizer_profile', None)
        return prof.organization_name if (prof and prof.organization_name) else (obj.organizer.full_name or obj.organizer.email)

    def get_destination_summary(self, obj):
        if obj.destination_summary:
            return obj.destination_summary
        if obj.settlement_account and obj.settlement_account.paypal_email:
            return f"PayPal ({obj.settlement_account.paypal_email})"
        return "PayPal Direct Transfer"

