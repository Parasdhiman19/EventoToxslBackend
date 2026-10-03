from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Q
from rest_framework import status, views, permissions
from rest_framework.response import Response

from accounts.permissions import IsSuperAdminUser
from accounts.models import User, OrganizerProfile, SettlementAccount
from events.models import Event, TicketTier, Seat
from tickets.models import Order, AttendeeTicket
from payouts.models import Payout
from .models import HomepageBanner, RecommendedEvent, AuditLog, PlatformReport, PlatformSetting
from .utils import log_admin_action
from .serializers import (
    HomepageBannerSerializer,
    RecommendedEventSerializer,
    AuditLogSerializer,
    PlatformReportSerializer,
    PlatformSettingSerializer,
    AdminUserListSerializer,
    AdminOrganizerSerializer,
    AdminEventListSerializer,
    AdminTransactionSerializer,
)


# =============================================================================
# 1. SUPER ADMIN DASHBOARD & ANALYTICS
# =============================================================================

class AdminDashboardStatsView(views.APIView):
    """
    Returns executive-level financial metrics, operational counts,
    time-window volume trajectory chart data, settlement allocations, and category breakdown.
    """
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        timeframe = request.query_params.get('range', '30d').lower()

        # 1. Financial Totals
        confirmed_orders = Order.objects.filter(status__in=['Confirmed', 'Paid', 'Completed'])
        refunded_orders = Order.objects.filter(status='Refunded')
        failed_orders = Order.objects.filter(status='Failed')

        gross_volume = confirmed_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        platform_fee_revenue = confirmed_orders.aggregate(total=Sum('fees'))['total'] or Decimal('0.00')
        refunded_volume = refunded_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        failed_count = failed_orders.count()

        # Disbursed Payouts
        disbursed_total = Payout.objects.filter(status='Completed').aggregate(total=Sum('net_disbursed'))['total'] or Decimal('0.00')
        pending_payouts_total = Payout.objects.filter(status__in=['Pending', 'Processing']).aggregate(total=Sum('gross_amount'))['total'] or Decimal('0.00')

        # Estimated Available Escrow in Platform
        pending_escrow = max(Decimal('0.00'), (gross_volume - platform_fee_revenue) - disbursed_total)

        # Time Window Sales
        today_sales = confirmed_orders.filter(created_at__gte=today_start).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        week_sales = confirmed_orders.filter(created_at__gte=week_start).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        month_sales = confirmed_orders.filter(created_at__gte=month_start).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

        # 2. Operational Counts
        total_users = User.objects.count()
        new_users_month = User.objects.filter(created_at__gte=month_start).count()
        active_organizers = OrganizerProfile.objects.count()
        suspended_users = User.objects.filter(is_suspended=True).count()

        total_events = Event.objects.count()
        live_events = Event.objects.filter(status='published').count()
        draft_events = Event.objects.filter(status='draft').count()
        flagged_events = Event.objects.filter(status='suspended').count()

        # Ticket Statistics
        total_tickets_sold = confirmed_orders.aggregate(qty=Sum('quantity'))['qty'] or 0
        total_checked_in = AttendeeTicket.objects.filter(is_checked_in=True).count()
        total_attendees = AttendeeTicket.objects.count()
        check_in_rate = round((total_checked_in / (total_attendees or 1)) * 100, 1) if total_attendees > 0 else 0.0

        # 3. Dynamic Velocity Time-Series Chart Data
        chart_data = []
        if timeframe == '7d':
            days_count = 7
            for i in range(days_count - 1, -1, -1):
                day_dt = (now - timedelta(days=i)).date()
                day_start_dt = timezone.datetime.combine(day_dt, timezone.datetime.min.time(), tzinfo=timezone.get_current_timezone())
                day_end_dt = timezone.datetime.combine(day_dt, timezone.datetime.max.time(), tzinfo=timezone.get_current_timezone())

                day_orders = confirmed_orders.filter(created_at__range=(day_start_dt, day_end_dt))
                day_gross = day_orders.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
                day_fee = day_orders.aggregate(s=Sum('fees'))['s'] or Decimal('0.00')
                day_tickets = day_orders.aggregate(q=Sum('quantity'))['q'] or 0

                chart_data.append({
                    'date': day_dt.strftime('%a, %b %d'),
                    'shortDate': day_dt.strftime('%b %d'),
                    'gross': float(day_gross),
                    'platformFee': float(day_fee),
                    'tickets': day_tickets,
                })
        elif timeframe == '90d':
            # 90 Days bucketed in 3-day intervals (30 data points)
            for i in range(29, -1, -1):
                interval_end = (now - timedelta(days=i * 3))
                interval_start = interval_end - timedelta(days=3)
                start_dt = timezone.datetime.combine(interval_start.date(), timezone.datetime.min.time(), tzinfo=timezone.get_current_timezone())
                end_dt = timezone.datetime.combine(interval_end.date(), timezone.datetime.max.time(), tzinfo=timezone.get_current_timezone())

                bucket_orders = confirmed_orders.filter(created_at__range=(start_dt, end_dt))
                b_gross = bucket_orders.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
                b_fee = bucket_orders.aggregate(s=Sum('fees'))['s'] or Decimal('0.00')
                b_tickets = bucket_orders.aggregate(q=Sum('quantity'))['q'] or 0

                chart_data.append({
                    'date': interval_end.strftime('%b %d'),
                    'shortDate': interval_end.strftime('%b %d'),
                    'gross': float(b_gross),
                    'platformFee': float(b_fee),
                    'tickets': b_tickets,
                })
        elif timeframe == '1y':
            # 12 Months
            for i in range(11, -1, -1):
                m_year = now.year
                m_month = now.month - i
                while m_month <= 0:
                    m_month += 12
                    m_year -= 1

                m_start = timezone.datetime(m_year, m_month, 1, tzinfo=timezone.get_current_timezone())
                if m_month == 12:
                    m_end = timezone.datetime(m_year + 1, 1, 1, tzinfo=timezone.get_current_timezone()) - timedelta(microseconds=1)
                else:
                    m_end = timezone.datetime(m_year, m_month + 1, 1, tzinfo=timezone.get_current_timezone()) - timedelta(microseconds=1)

                m_orders = confirmed_orders.filter(created_at__range=(m_start, m_end))
                m_gross = m_orders.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
                m_fee = m_orders.aggregate(s=Sum('fees'))['s'] or Decimal('0.00')
                m_tickets = m_orders.aggregate(q=Sum('quantity'))['q'] or 0

                chart_data.append({
                    'date': m_start.strftime('%B %Y'),
                    'shortDate': m_start.strftime('%b \'%y'),
                    'gross': float(m_gross),
                    'platformFee': float(m_fee),
                    'tickets': m_tickets,
                })
        else: # Default 30 Days
            for i in range(29, -1, -1):
                day_dt = (now - timedelta(days=i)).date()
                day_start_dt = timezone.datetime.combine(day_dt, timezone.datetime.min.time(), tzinfo=timezone.get_current_timezone())
                day_end_dt = timezone.datetime.combine(day_dt, timezone.datetime.max.time(), tzinfo=timezone.get_current_timezone())

                day_orders = confirmed_orders.filter(created_at__range=(day_start_dt, day_end_dt))
                day_gross = day_orders.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
                day_fee = day_orders.aggregate(s=Sum('fees'))['s'] or Decimal('0.00')
                day_tickets = day_orders.aggregate(q=Sum('quantity'))['q'] or 0

                chart_data.append({
                    'date': day_dt.strftime('%b %d, %Y'),
                    'shortDate': day_dt.strftime('%b %d'),
                    'gross': float(day_gross),
                    'platformFee': float(day_fee),
                    'tickets': day_tickets,
                })

        # 4. Category Breakdown & Share
        categories_agg = list(Event.objects.filter(status='published').values('category').annotate(
            count=Count('id')
        ).order_by('-count'))
        total_cat_events = sum(c['count'] for c in categories_agg) or 1
        for cat in categories_agg:
            cat['percentage'] = round((cat['count'] / total_cat_events) * 100, 1)

        return Response({
            'financials': {
                'grossVolume': f"${float(gross_volume):,.2f}",
                'grossVolumeRaw': float(gross_volume),
                'platformFeeRevenue': f"${float(platform_fee_revenue):,.2f}",
                'platformFeeRaw': float(platform_fee_revenue),
                'organizerNet': f"${float(gross_volume - platform_fee_revenue):,.2f}",
                'disbursedTotal': f"${float(disbursed_total):,.2f}",
                'pendingEscrow': f"${float(pending_escrow):,.2f}",
                'pendingPayouts': f"${float(pending_payouts_total):,.2f}",
                'refundedVolume': f"${float(refunded_volume):,.2f}",
                'failedCount': failed_count,
                'todaySales': f"${float(today_sales):,.2f}",
                'weekSales': f"${float(week_sales):,.2f}",
                'monthSales': f"${float(month_sales):,.2f}",
            },
            'settlementAllocation': {
                'gross': float(gross_volume),
                'disbursed': float(disbursed_total),
                'platformFee': float(platform_fee_revenue),
                'pendingEscrow': float(pending_escrow),
                'pendingPayouts': float(pending_payouts_total),
                'refunded': float(refunded_volume),
            },
            'admissionsFunnel': {
                'totalTickets': total_attendees,
                'checkedIn': total_checked_in,
                'pending': max(0, total_attendees - total_checked_in),
                'checkInRate': check_in_rate,
            },
            'operations': {
                'totalUsers': total_users,
                'newUsersThisMonth': new_users_month,
                'activeOrganizers': active_organizers,
                'suspendedUsers': suspended_users,
                'totalEvents': total_events,
                'liveEvents': live_events,
                'draftEvents': draft_events,
                'flaggedEvents': flagged_events,
                'totalTicketsSold': total_tickets_sold,
                'totalCheckedIn': total_checked_in,
                'checkInRate': f"{check_in_rate}%",
            },
            'revenueChart': chart_data,
            'timeframe': timeframe,
            'categoryBreakdown': categories_agg,
        })


class AdminRecentActivityView(views.APIView):
    """
    Real-time feed of recent orders, registrations, and check-ins.
    """
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        recent_orders = Order.objects.order_by('-created_at')[:8]
        recent_checkins = AttendeeTicket.objects.filter(is_checked_in=True).order_by('-checked_in_at')[:6]
        recent_users = User.objects.order_by('-created_at')[:6]

        activities = []
        for o in recent_orders:
            activities.append({
                'type': 'order',
                'title': f"Order #{o.order_number} ({o.status})",
                'description': f"{o.user.full_name or o.user.email} purchased {o.quantity}x {o.tier.name if o.tier else 'tickets'} for ${float(o.total_amount):,.2f}",
                'time': o.created_at.isoformat() if o.created_at else None,
                'status': o.status,
            })

        for c in recent_checkins:
            activities.append({
                'type': 'checkin',
                'title': f"Gate Check-in: {c.attendee_name}",
                'description': f"Admitted to '{c.event.title}' ({c.seat_or_gate})",
                'time': c.checked_in_at.isoformat() if c.checked_in_at else None,
                'status': 'Admitted',
            })

        for u in recent_users:
            activities.append({
                'type': 'user',
                'title': f"New User: {u.full_name or u.email}",
                'description': f"Registered with role '{u.role}'",
                'time': u.created_at.isoformat() if u.created_at else None,
                'status': 'Active',
            })

        # Sort combined stream by timestamp desc
        activities.sort(key=lambda x: x.get('time') or '', reverse=True)

        return Response({'activities': activities[:15]})


# =============================================================================
# 2. HOMEPAGE BANNER MANAGEMENT
# =============================================================================

class AdminBannerListCreateView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        banners = HomepageBanner.objects.all().select_related('event')
        return Response(HomepageBannerSerializer(banners, many=True).data)

    def post(self, request):
        serializer = HomepageBannerSerializer(data=request.data)
        if serializer.is_valid():
            banner = serializer.save()
            log_admin_action(
                request,
                action_type="CREATE_BANNER",
                target_model="HomepageBanner",
                target_id=banner.id,
                description=f"Created homepage banner: '{banner.title}'"
            )
            return Response(HomepageBannerSerializer(banner).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminBannerDetailView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get_object(self, pk):
        return HomepageBanner.objects.filter(pk=pk).first()

    def get(self, request, pk):
        banner = self.get_object(pk)
        if not banner:
            return Response({'detail': 'Banner not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(HomepageBannerSerializer(banner).data)

    def patch(self, request, pk):
        banner = self.get_object(pk)
        if not banner:
            return Response({'detail': 'Banner not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = HomepageBannerSerializer(banner, data=request.data, partial=True)
        if serializer.is_valid():
            updated_banner = serializer.save()
            log_admin_action(
                request,
                action_type="UPDATE_BANNER",
                target_model="HomepageBanner",
                target_id=banner.id,
                description=f"Updated banner #{banner.id}: '{updated_banner.title}'",
                changes=request.data
            )
            return Response(HomepageBannerSerializer(updated_banner).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        banner = self.get_object(pk)
        if not banner:
            return Response({'detail': 'Banner not found.'}, status=status.HTTP_404_NOT_FOUND)
        title = banner.title
        banner.delete()
        log_admin_action(
            request,
            action_type="DELETE_BANNER",
            target_model="HomepageBanner",
            target_id=pk,
            description=f"Deleted banner #{pk}: '{title}'"
        )
        return Response({'detail': 'Banner deleted successfully.'}, status=status.HTTP_200_OK)


class AdminBannerReorderView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def post(self, request):
        order_list = request.data.get('order', [])
        for item in order_list:
            b_id = item.get('id')
            pos = item.get('display_order', item.get('displayOrder', 1))
            HomepageBanner.objects.filter(pk=b_id).update(display_order=pos)

        log_admin_action(
            request,
            action_type="REORDER_BANNERS",
            target_model="HomepageBanner",
            description=f"Reordered {len(order_list)} homepage banners."
        )
        return Response({'detail': 'Banner sequence updated successfully.'}, status=status.HTTP_200_OK)


# =============================================================================
# 3. RECOMMENDED EVENTS MANAGEMENT
# =============================================================================

class AdminRecommendedEventListCreateView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        entries = RecommendedEvent.objects.all().select_related('event', 'event__organizer')
        return Response(RecommendedEventSerializer(entries, many=True).data)

    def post(self, request):
        serializer = RecommendedEventSerializer(data=request.data)
        if serializer.is_valid():
            entry = serializer.save()
            log_admin_action(
                request,
                action_type="ADD_RECOMMENDED_EVENT",
                target_model="RecommendedEvent",
                target_id=entry.id,
                description=f"Added '{entry.event.title}' to recommended list at rank #{entry.priority_rank}."
            )
            return Response(RecommendedEventSerializer(entry).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminRecommendedEventDetailView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def delete(self, request, pk):
        entry = RecommendedEvent.objects.filter(pk=pk).first()
        if not entry:
            return Response({'detail': 'Recommended entry not found.'}, status=status.HTTP_404_NOT_FOUND)
        event_title = entry.event.title
        entry.delete()
        log_admin_action(
            request,
            action_type="REMOVE_RECOMMENDED_EVENT",
            target_model="RecommendedEvent",
            target_id=pk,
            description=f"Removed '{event_title}' from recommended events list."
        )
        return Response({'detail': 'Recommended event entry removed.'}, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        entry = RecommendedEvent.objects.filter(pk=pk).first()
        if not entry:
            return Response({'detail': 'Recommended entry not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RecommendedEventSerializer(entry, data=request.data, partial=True)
        if serializer.is_valid():
            updated_entry = serializer.save()
            return Response(RecommendedEventSerializer(updated_entry).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminRecommendedEventReorderView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def post(self, request):
        ranks = request.data.get('order', [])
        for item in ranks:
            r_id = item.get('id')
            rank = item.get('priority_rank', item.get('priorityRank', 1))
            RecommendedEvent.objects.filter(pk=r_id).update(priority_rank=rank)

        log_admin_action(
            request,
            action_type="REORDER_RECOMMENDED_EVENTS",
            target_model="RecommendedEvent",
            description=f"Updated priority ranks for {len(ranks)} recommended events."
        )
        return Response({'detail': 'Recommended events priority updated.'}, status=status.HTTP_200_OK)


# =============================================================================
# 4. EVENT OVERSIGHT & MODERATION
# =============================================================================

class AdminEventListView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        events = Event.objects.all().select_related(
            'organizer',
            'organizer__organizer_profile'
        ).prefetch_related(
            'tiers'
        ).annotate(
            annotated_checked_in=Count('attendees', filter=Q(attendees__is_checked_in=True))
        )

        # Filters
        status_filter = request.query_params.get('status')
        if status_filter and status_filter != 'all':
            events = events.filter(status=status_filter)

        category_filter = request.query_params.get('category')
        if category_filter and category_filter != 'all':
            events = events.filter(category__iexact=category_filter)

        search = request.query_params.get('search')
        if search:
            events = events.filter(
                Q(title__icontains=search) |
                Q(organizer__full_name__icontains=search) |
                Q(organizer__email__icontains=search) |
                Q(city__icontains=search) |
                Q(venue_name__icontains=search)
            )

        events = events.order_by('-created_at')
        return Response(AdminEventListSerializer(events, many=True, context={'request': request}).data)


class AdminEventDetailView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request, pk):
        event = Event.objects.filter(pk=pk).select_related('organizer').prefetch_related('tiers', 'seats').first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        orders = Order.objects.filter(event=event).select_related('user')
        attendees = AttendeeTicket.objects.filter(event=event)

        tiers_data = []
        for t in event.tiers.all():
            tiers_data.append({
                'id': t.id,
                'name': t.name,
                'price': f"${float(t.price):,.2f}",
                'capacity': t.capacity,
                'sold': t.sold_count,
                'remaining': max(0, t.capacity - t.sold_count),
                'revenue': f"${float(t.price * t.sold_count):,.2f}"
            })

        return Response({
            'event': AdminEventListSerializer(event, context={'request': request}).data,
            'description': event.description,
            'hasAssignedSeating': event.has_assigned_seating,
            'seatingLayout': event.seating_layout,
            'tiers': tiers_data,
            'totalOrders': orders.count(),
            'totalAttendees': attendees.count(),
            'checkedInAttendees': attendees.filter(is_checked_in=True).count(),
        })


class AdminEventStatusView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def patch(self, request, pk):
        event = Event.objects.filter(pk=pk).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        reason = request.data.get('reason', 'Administrative decision')

        valid_statuses = ['published', 'draft', 'past', 'cancelled', 'suspended']
        if new_status not in valid_statuses:
            return Response({'detail': f'Invalid status. Must be one of: {valid_statuses}'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = event.status
        event.status = new_status
        event.save(update_fields=['status'])

        log_admin_action(
            request,
            action_type="CHANGE_EVENT_STATUS",
            target_model="Event",
            target_id=event.id,
            description=f"Changed status of '{event.title}' from '{old_status}' to '{new_status}'. Reason: {reason}",
            changes={'oldStatus': old_status, 'newStatus': new_status, 'reason': reason}
        )

        return Response({
            'detail': f"Event status updated to {new_status}.",
            'status': new_status
        })


class AdminEventToggleFeaturedView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def post(self, request, pk):
        event = Event.objects.filter(pk=pk).first()
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        event.is_featured = not event.is_featured
        event.save(update_fields=['is_featured'])

        log_admin_action(
            request,
            action_type="TOGGLE_FEATURED_EVENT",
            target_model="Event",
            target_id=event.id,
            description=f"{'Featured' if event.is_featured else 'Unfeatured'} event '{event.title}'."
        )

        return Response({
            'isFeatured': event.is_featured,
            'detail': f"Event {'promoted to featured' if event.is_featured else 'removed from featured'}."
        })


# =============================================================================
# 5. USER & ORGANIZER MANAGEMENT
# =============================================================================

class AdminUserListView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        users = User.objects.all().prefetch_related('orders', 'organizer_profile')

        role_filter = request.query_params.get('role')
        if role_filter and role_filter != 'all':
            users = users.filter(role=role_filter)

        status_filter = request.query_params.get('status')
        if status_filter == 'suspended':
            users = users.filter(is_suspended=True)
        elif status_filter == 'active':
            users = users.filter(is_suspended=False)

        search = request.query_params.get('search')
        if search:
            users = users.filter(
                Q(email__icontains=search) |
                Q(full_name__icontains=search) |
                Q(username__icontains=search) |
                Q(phone__icontains=search)
            )

        users = users.order_by('-created_at')
        return Response(AdminUserListSerializer(users, many=True).data)


class AdminUserSuspendView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def post(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.is_superuser:
            return Response({'detail': 'Superuser accounts cannot be suspended.'}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason', 'Administrative suspension')
        user.is_suspended = True
        user.suspension_reason = reason
        user.save(update_fields=['is_suspended', 'suspension_reason'])

        log_admin_action(
            request,
            action_type="SUSPEND_USER",
            target_model="User",
            target_id=user.id,
            description=f"Suspended user account {user.email}. Reason: {reason}",
            changes={'reason': reason}
        )

        return Response({'detail': f'User {user.email} suspended.', 'isSuspended': True})


class AdminUserUnsuspendView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def post(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        user.is_suspended = False
        user.suspension_reason = ''
        user.save(update_fields=['is_suspended', 'suspension_reason'])

        log_admin_action(
            request,
            action_type="UNSUSPEND_USER",
            target_model="User",
            target_id=user.id,
            description=f"Restored user account {user.email} from suspension."
        )

        return Response({'detail': f'User {user.email} restored.', 'isSuspended': False})


class AdminUserRoleView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def patch(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_role = request.data.get('role')
        if new_role not in ['user', 'manager', 'admin']:
            return Response({'detail': 'Invalid role.'}, status=status.HTTP_400_BAD_REQUEST)

        old_role = user.role
        user.role = new_role
        if new_role == 'admin':
            user.is_staff = True
        user.save(update_fields=['role', 'is_staff'])

        log_admin_action(
            request,
            action_type="CHANGE_USER_ROLE",
            target_model="User",
            target_id=user.id,
            description=f"Changed role for {user.email} from {old_role} to {new_role}."
        )

        return Response({'detail': f"Role updated to {new_role}.", 'role': new_role})


class AdminOrganizerListView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        organizers = OrganizerProfile.objects.all().select_related('user')
        search = request.query_params.get('search')
        if search:
            organizers = organizers.filter(
                Q(organization_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__full_name__icontains=search) |
                Q(handle__icontains=search)
            )

        return Response(AdminOrganizerSerializer(organizers, many=True).data)


# =============================================================================
# 6. TRANSACTIONS, ORDERS & PAYOUTS
# =============================================================================

class AdminTransactionListView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        orders = Order.objects.all().select_related('user', 'event', 'tier', 'event__organizer')

        status_filter = request.query_params.get('status')
        if status_filter and status_filter != 'all':
            orders = orders.filter(status__iexact=status_filter)

        search = request.query_params.get('search')
        if search:
            orders = orders.filter(
                Q(order_number__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__full_name__icontains=search) |
                Q(paypal_capture_id__icontains=search) |
                Q(event__title__icontains=search)
            )

        orders = orders.order_by('-created_at')
        return Response(AdminTransactionSerializer(orders, many=True).data)


class AdminPayoutListView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        from .serializers import AdminPayoutSerializer
        payouts = Payout.objects.all().select_related('organizer', 'settlement_account')

        status_filter = request.query_params.get('status')
        if status_filter and status_filter != 'all':
            payouts = payouts.filter(status=status_filter)

        payouts = payouts.order_by('-created_at')
        return Response(AdminPayoutSerializer(payouts, many=True).data)


class AdminPayoutProcessView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def post(self, request, pk):
        payout = Payout.objects.filter(pk=pk).first()
        if not payout:
            return Response({'detail': 'Payout request not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')  # 'approve' or 'reject'
        notes = request.data.get('notes', '')

        if action == 'approve':
            payout.status = 'Completed'
            if notes:
                payout.failure_reason = notes
            payout.save()
            log_admin_action(
                request,
                action_type="APPROVE_PAYOUT",
                target_model="Payout",
                target_id=payout.id,
                description=f"Approved payout #{payout.payout_number} of ${float(payout.net_disbursed):,.2f} for {payout.organizer.email}."
            )
            return Response({'detail': 'Payout marked as Completed.', 'status': 'Completed'})

        elif action == 'reject':
            payout.status = 'Failed'
            payout.failure_reason = notes or 'Rejected by Super Admin'
            payout.save()
            log_admin_action(
                request,
                action_type="REJECT_PAYOUT",
                target_model="Payout",
                target_id=payout.id,
                description=f"Rejected payout #{payout.payout_number} for {payout.organizer.email}. Reason: {payout.failure_reason}"
            )
            return Response({'detail': 'Payout marked as Failed/Rejected.', 'status': 'Failed'})

        return Response({'detail': 'Invalid action. Must be approve or reject.'}, status=status.HTTP_400_BAD_REQUEST)


# =============================================================================
# 7. ATTENDANCE & GATE SCANNER MONITORING
# =============================================================================

class AdminAttendanceListView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        events = Event.objects.filter(status='published').order_by('-date')

        attendance_data = []
        for ev in events:
            attendees = AttendeeTicket.objects.filter(event=ev)
            total = attendees.count()
            checked_in = attendees.filter(is_checked_in=True).count()
            rate = round((checked_in / (total or 1)) * 100, 1) if total > 0 else 0.0

            attendance_data.append({
                'eventId': ev.id,
                'eventTitle': ev.title,
                'date': ev.date.strftime('%b %d, %Y') if ev.date else 'TBA',
                'venue': ev.venue_name or ev.city or 'Online',
                'organizer': ev.organizer.full_name or ev.organizer.email,
                'totalAttendees': total,
                'checkedIn': checked_in,
                'pending': total - checked_in,
                'rate': f"{rate}%",
                'rateRaw': rate,
            })

        return Response({'events': attendance_data})


# =============================================================================
# 8. REPORTS & MODERATION
# =============================================================================

class AdminPlatformReportListView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        reports = PlatformReport.objects.all().select_related('reporter', 'resolved_by').order_by('-created_at')
        return Response(PlatformReportSerializer(reports, many=True).data)

    def post(self, request):
        serializer = PlatformReportSerializer(data=request.data)
        if serializer.is_valid():
            report = serializer.save(reporter=request.user)
            return Response(PlatformReportSerializer(report).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminPlatformReportDetailView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def patch(self, request, pk):
        report = PlatformReport.objects.filter(pk=pk).first()
        if not report:
            return Response({'detail': 'Report not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        resolution_notes = request.data.get('resolution_notes', request.data.get('resolutionNotes', ''))

        if new_status:
            report.status = new_status
        if resolution_notes:
            report.resolution_notes = resolution_notes

        report.resolved_by = request.user
        report.resolved_at = timezone.now()
        report.save()

        log_admin_action(
            request,
            action_type="RESOLVE_REPORT",
            target_model="PlatformReport",
            target_id=report.id,
            description=f"Marked report #{report.id} as '{report.status}'."
        )

        return Response(PlatformReportSerializer(report).data)


# =============================================================================
# 9. PLATFORM SETTINGS & AUDIT LOGS
# =============================================================================

class AdminPlatformSettingsView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        settings_qs = PlatformSetting.objects.all()
        # Seed defaults if empty
        defaults = {
            'platform_fee_percentage': ('3.5', 'number', 'Platform fee charged per ticket sale'),
            'platform_support_email': ('support@evento.com', 'string', 'Primary support and operations inbox'),
            'platform_name': ('Evento', 'string', 'Public brand name'),
            'seat_hold_timeout_minutes': ('10', 'number', 'Duration in minutes to hold seats during checkout'),
            'maintenance_mode': ('false', 'boolean', 'Toggle platform maintenance banner'),
        }
        for k, (v, dt, desc) in defaults.items():
            if not PlatformSetting.objects.filter(key=k).exists():
                PlatformSetting.objects.create(key=k, value=v, data_type=dt, description=desc)

        settings_qs = PlatformSetting.objects.all()
        return Response(PlatformSettingSerializer(settings_qs, many=True).data)

    def patch(self, request):
        updates = request.data.get('settings', {})
        for k, v in updates.items():
            PlatformSetting.objects.filter(key=k).update(value=str(v))

        log_admin_action(
            request,
            action_type="UPDATE_PLATFORM_SETTINGS",
            target_model="PlatformSetting",
            description="Updated platform-wide business settings.",
            changes=updates
        )

        return Response({'detail': 'Settings updated successfully.'})


class AdminAuditLogListView(views.APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        logs = AuditLog.objects.all().select_related('actor')
        action_filter = request.query_params.get('action')
        if action_filter:
            logs = logs.filter(action_type__icontains=action_filter)

        search = request.query_params.get('search')
        if search:
            logs = logs.filter(
                Q(description__icontains=search) |
                Q(actor__email__icontains=search) |
                Q(target_id__icontains=search)
            )

        logs = logs.order_by('-created_at')[:100]
        return Response(AuditLogSerializer(logs, many=True).data)


# =============================================================================
# 10. PUBLIC HOMEPAGE CONTENT ENDPOINT
# =============================================================================

class PublicHomepageContentView(views.APIView):
    """
    Public endpoint returning currently active banners and curated recommended events.
    Used by public frontend discovery and landing pages.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        now = timezone.now()

        # 1. Active Banners
        banners = HomepageBanner.objects.filter(
            is_active=True
        ).filter(
            Q(active_from__isnull=True) | Q(active_from__lte=now)
        ).filter(
            Q(active_until__isnull=True) | Q(active_until__gte=now)
        ).order_by('display_order', '-created_at').select_related('event')

        # 2. Active Recommended Events
        recommended_entries = RecommendedEvent.objects.filter(
            is_active=True,
            event__status='published'
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now)
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        ).order_by('priority_rank', '-created_at').select_related('event', 'event__organizer')

        return Response({
            'banners': HomepageBannerSerializer(banners, many=True).data,
            'recommendations': RecommendedEventSerializer(recommended_entries, many=True).data
        })
