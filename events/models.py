from django.db import models
from django.conf import settings


class Event(models.Model):
    CATEGORY_CHOICES = (
        ('Music & Concerts', 'Music & Concerts'),
        ('Tech & Conferences', 'Tech & Conferences'),
        ('Food & Tasting', 'Food & Tasting'),
        ('Nightlife', 'Nightlife'),
        ('Art & Exhibitions', 'Art & Exhibitions'),
        ('Workshops', 'Workshops'),
        ('Conference', 'Conference'),
        ('Exhibition & Tasting', 'Exhibition & Tasting'),
        ('Club Night', 'Club Night'),
    )

    STATUS_CHOICES = (
        ('published', 'Published'),
        ('draft', 'Draft'),
        ('past', 'Past / Archived'),
    )

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='events'
    )
    title = models.CharField(max_length=255, unique=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default='Music & Concerts')
    description = models.TextField(blank=True)
    banner_image = models.ImageField(upload_to='events/banners/', blank=True, null=True)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    venue_name = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, default='Chandigarh')
    address = models.CharField(max_length=255, blank=True)
    is_online = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    is_featured = models.BooleanField(default=False)
    has_assigned_seating = models.BooleanField(default=True)
    seating_layout = models.JSONField(default=dict, blank=True)

    # Event Ticketing & Checkout Policy Snapshots (Inherited from Organizer Defaults upon Creation)
    pass_platform_fee_to_buyer = models.BooleanField(default=True)
    allow_ticket_transfers = models.BooleanField(default=True)
    require_attendee_phone = models.BooleanField(default=True)
    auto_refund_cancelled_events = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-start_time']

    @property
    def is_ended(self):
        """
        Calculates whether this event has expired/ended based on date and end_time (or start_time).
        Uses Django's timezone-aware current time.
        """
        if self.status == 'past':
            return True
        import datetime
        from django.utils import timezone
        now = timezone.localtime(timezone.now()) if timezone.is_aware(timezone.now()) else timezone.now()
        event_time = self.end_time or self.start_time or datetime.time(23, 59, 59)
        event_dt = datetime.datetime.combine(self.date, event_time)
        if timezone.is_aware(now):
            tz = timezone.get_current_timezone()
            event_dt = timezone.make_aware(event_dt, tz) if timezone.is_naive(event_dt) else event_dt
        return now > event_dt

    @property
    def computed_status(self):
        """
        Returns the source-of-truth computed status:
        - 'draft' if manually marked draft
        - 'past' if marked past or the event date & time has passed (Ended)
        - 'published' otherwise
        """
        if self.status == 'draft':
            return 'draft'
        if self.status == 'past' or self.is_ended:
            return 'past'
        return 'published'

    def __str__(self):
        return f"{self.title} ({self.date})"


class TicketTier(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tiers')
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    capacity = models.PositiveIntegerField(default=100)
    sold_count = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.name} - ${self.price} ({self.event.title})"


class Seat(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('reserved', 'Temporarily Reserved'),
        ('booked', 'Booked / Sold'),
        ('blocked', 'Blocked / Unavailable'),
    )

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='seats')
    tier = models.ForeignKey(TicketTier, on_delete=models.CASCADE, related_name='seats', null=True, blank=True)
    section_name = models.CharField(max_length=100, default='Main Hall')
    row = models.CharField(max_length=10)
    seat_number = models.CharField(max_length=10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_accessible = models.BooleanField(default=False)
    reserved_until = models.DateTimeField(null=True, blank=True)
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='held_seats'
    )

    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='booked_seats'
    )
    order = models.ForeignKey(
        'tickets.Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='seats'
    )
    ticket = models.OneToOneField(
        'tickets.AttendeeTicket',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_seat'
    )

    class Meta:
        unique_together = ('event', 'section_name', 'row', 'seat_number')
        ordering = ['row', 'seat_number']

    def __str__(self):
        return f"{self.event.title} - {self.section_name} [{self.row}{self.seat_number}] ({self.status})"


class SavedEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_events'
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='saved_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'event')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} saved {self.event.title}"


class EventStaff(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='staff_members'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_assignments'
    )
    role_title = models.CharField(
        max_length=100,
        default='Stage Coordinator',
        blank=True,
        help_text="Designation or gate responsibility title for this event."
    )
    can_view_attendees = models.BooleanField(
        default=True,
        help_text="Allows viewing guest list and attendee details for this event."
    )
    can_check_in = models.BooleanField(
        default=True,
        help_text="Allows scanning and toggling admission check-in status at the gate."
    )
    can_edit_attendees = models.BooleanField(
        default=False,
        help_text="Allows modifying attendee information or notes."
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('event', 'user')
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.user.email} (Staff on {self.event.title})"


class EventLike(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_likes'
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'event'], name='unique_user_event_like')
        ]
        indexes = [
            models.Index(fields=['event', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} liked {self.event.title}"


class EventComment(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_comments'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    content = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['event', 'parent', 'created_at']),
        ]
        ordering = ['created_at']

    def __str__(self):
        status_suffix = " [DELETED]" if self.is_deleted else ""
        return f"Comment by {self.user.email} on {self.event.title}{status_suffix}"


class CommentLike(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comment_likes'
    )
    comment = models.ForeignKey(
        EventComment,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'comment'], name='unique_user_comment_like')
        ]
        indexes = [
            models.Index(fields=['comment', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} liked comment #{self.comment_id}"

