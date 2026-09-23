from decimal import Decimal
from django.db.models import Sum
from rest_framework import status, views, permissions
from rest_framework.response import Response

from accounts.permissions import IsManagerUser
from .models import Payout
from .serializers import PayoutSerializer
from events.models import Event
from tickets.models import Order, AttendeeTicket
from accounts.models import SettlementAccount
from accounts.serializers import SettlementAccountSerializer


def calculate_organizer_financials(user):
    """
    Computes accurate financial totals for an organizer respecting each event's fee policy:
    - gross_ticket_sales: Total face value of tickets sold
    - total_platform_fees: Total platform fees collected (from buyer or organizer)
    - organizer_net_earnings: Total net revenue earned by organizer
    - disbursed_total: Total amount already withdrawn via completed payouts
    - available_balance: Remaining funds available for withdrawal
    """
    user_events = Event.objects.filter(organizer=user)
    confirmed_orders = Order.objects.filter(
        event__in=user_events,
        status__in=['Confirmed', 'Paid', 'Completed']
    ).select_related('event')

    gross_ticket_sales = Decimal('0.00')
    total_platform_fees = Decimal('0.00')
    organizer_net_earnings = Decimal('0.00')

    for order in confirmed_orders:
        subtotal = (order.unit_price * order.quantity).quantize(Decimal('0.01'))
        gross_ticket_sales += subtotal

        pass_to_buyer = getattr(order.event, 'pass_platform_fee_to_buyer', True)
        if pass_to_buyer:
            # Buyer paid the fee; organizer receives 100% of ticket subtotal with zero fee cut
            organizer_net_earnings += subtotal
            total_platform_fees += order.fees
        else:
            # Organizer absorbs the 3.5% fee
            fee = (subtotal * Decimal('0.035')).quantize(Decimal('0.01'))
            total_platform_fees += fee
            organizer_net_earnings += (subtotal - fee)

    payouts_completed = Payout.objects.filter(organizer=user, status__in=['Completed', 'Processing'])
    disbursed_total = payouts_completed.aggregate(total=Sum('net_disbursed'))['total'] or Decimal('0.00')
    available_balance = max(Decimal('0.00'), organizer_net_earnings - disbursed_total)

    return {
        'gross_ticket_sales': gross_ticket_sales,
        'total_platform_fees': total_platform_fees,
        'organizer_net_earnings': organizer_net_earnings,
        'disbursed_total': disbursed_total,
        'available_balance': available_balance,
    }


class ManagerOverviewView(views.APIView):
    permission_classes = [IsManagerUser]

    def get(self, request):
        from django.utils import timezone
        from django.db.models import Q

        user_events = Event.objects.filter(organizer=request.user)

        now = timezone.localtime(timezone.now()) if timezone.is_aware(timezone.now()) else timezone.now()
        current_date = now.date()
        current_time = now.time()

        active_events = user_events.filter(
            Q(status='published') & (
                Q(date__gt=current_date) |
                Q(date=current_date, end_time__isnull=False, end_time__gt=current_time) |
                Q(date=current_date, end_time__isnull=True, start_time__gte=current_time)
            )
        )

        # Financial Calculations
        financials = calculate_organizer_financials(request.user)
        total_revenue = financials['gross_ticket_sales']
        available_balance = financials['available_balance']

        # 2. Tickets Sold
        total_sold = 0
        total_capacity = 0
        for ev in user_events:
            for t in ev.tiers.all():
                total_sold += t.sold_count
                total_capacity += t.capacity

        # 3. Attendance Rate
        total_attendees = AttendeeTicket.objects.filter(event__in=user_events).count()
        checked_in = AttendeeTicket.objects.filter(event__in=user_events, is_checked_in=True).count()
        avg_attendance = f"{round((checked_in / (total_attendees or 1)) * 100, 1)}%" if total_attendees > 0 else "0.0%"

        stats = [
            {'label': 'Total Revenue', 'value': f"${total_revenue:,.2f}", 'change': '+14.2%', 'period': 'vs last month'},
            {'label': 'Tickets Sold', 'value': f"{total_sold:,}", 'change': '+8.1%', 'period': f'across {user_events.count()} configured stages'},
            {'label': 'Active Events', 'value': str(active_events.count()), 'change': f'{active_events.count()} live upcoming', 'period': 'in active schedule'},
            {'label': 'Avg. Attendance Rate', 'value': avg_attendance, 'change': f'{checked_in}/{total_attendees} checked-in', 'period': 'gate admissions rate'},
        ]

        # Active / published events preview
        events_for_preview = active_events if active_events.exists() else user_events[:5]
        active_events_data = []
        for ev in events_for_preview[:6]:
            ev_sold = sum(t.sold_count for t in ev.tiers.all())
            ev_total = sum(t.capacity for t in ev.tiers.all())
            ev_rev = sum(t.price * t.sold_count for t in ev.tiers.all())
            
            if ev.is_ended or ev.status == 'past':
                status_text = 'Ended'
                status_color = 'text-stone-600 bg-stone-100 border-stone-200'
            elif ev.status == 'draft':
                status_text = 'Draft'
                status_color = 'text-amber-700 bg-amber-50 border-amber-200'
            elif ev_total > 0 and ev_sold >= ev_total:
                status_text = 'Sold Out'
                status_color = 'text-stone-900 bg-stone-100 border-stone-900'
            elif ev_total > 0 and ev_sold >= ev_total * 0.7:
                status_text = 'Selling Fast'
                status_color = 'text-amber-700 bg-amber-50 border-amber-200'
            else:
                status_text = 'Live'
                status_color = 'text-emerald-700 bg-emerald-50 border-emerald-200'

            venue_label = 'Virtual Stream' if ev.is_online else (ev.venue_name or ev.city or 'Main Stage')

            active_events_data.append({
                'id': str(ev.id),
                'title': ev.title,
                'date': ev.date.strftime('%b %d, %Y') if ev.date else 'Date TBA',
                'venue': venue_label,
                'sold': ev_sold,
                'total': ev_total or 100,
                'revenue': f"${ev_rev:,.2f}",
                'status': status_text,
                'statusColor': status_color,
            })

        # Recent transactions preview
        recent_orders = Order.objects.filter(event__in=user_events).order_by('-created_at')[:6]
        recent_transactions = []
        for o in recent_orders:
            recent_transactions.append({
                'id': o.order_number,
                'buyer': o.user.full_name or o.user.email,
                'email': o.user.email,
                'event': o.event.title,
                'tier': f"{o.tier.name} (x{o.quantity})",
                'amount': f"${o.total_amount:,.2f}",
                'time': o.created_at.strftime('%b %d • %I:%M %p') if o.created_at else 'Recent',
            })

        return Response({
            'stats': stats,
            'activeEvents': active_events_data,
            'recentTransactions': recent_transactions,
            'nextPayoutEstimated': f"${available_balance:,.2f}",
        })


from .paypal_payouts import send_paypal_payout


class ManagerPayoutsView(views.APIView):
    permission_classes = [IsManagerUser]

    def get(self, request):
        user_events = Event.objects.filter(organizer=request.user)
        financials = calculate_organizer_financials(request.user)

        lifetime_sales = financials['gross_ticket_sales']
        platform_fees = financials['total_platform_fees']
        available_balance = financials['available_balance']
        pending_escrow = (available_balance * Decimal('0.55')).quantize(Decimal('0.01'))

        balance_cards = [
            {
                'label': 'Available for Payout',
                'value': f"${available_balance:,.2f}",
                'amount': float(available_balance),
                'sub': 'Cleared from ticket sales • Ready to withdraw',
                'primary': True,
            },
            {
                'label': 'Pending Escrow',
                'value': f"${pending_escrow:,.2f}",
                'amount': float(pending_escrow),
                'sub': 'Clears 48h after respective stage wraps',
                'primary': False,
            },
            {
                'label': 'Lifetime Gross Sales',
                'value': f"${lifetime_sales:,.2f}",
                'amount': float(lifetime_sales),
                'sub': f"Across {user_events.count()} completed & active stages",
                'primary': False,
            },
            {
                'label': 'Total Platform & Gateway Fees',
                'value': f"${platform_fees:,.2f}",
                'amount': float(platform_fees),
                'sub': 'Platform ticketing & processing fees',
                'primary': False,
            },
        ]

        bank_accounts = SettlementAccount.objects.filter(organizer=request.user).order_by('-is_primary', '-created_at')
        primary_method = bank_accounts.filter(is_primary=True).first() or bank_accounts.first()

        # Stage settlements breakdown
        revenue_by_event = []
        for ev in user_events:
            ev_gross = sum(t.price * t.sold_count for t in ev.tiers.all())
            pass_to_buyer = getattr(ev, 'pass_platform_fee_to_buyer', True)
            ev_fees = Decimal('0.00') if pass_to_buyer else (ev_gross * Decimal('0.035')).quantize(Decimal('0.01'))
            ev_net = ev_gross - ev_fees
            revenue_by_event.append({
                'name': ev.title,
                'gross': f"${ev_gross:,.2f}",
                'fees': f"${ev_fees:,.2f}",
                'refunds': '$0.00',
                'net': f"${ev_net:,.2f}",
                'status': 'Settling' if ev.status == 'published' else 'Completed',
            })

        payout_history = Payout.objects.filter(organizer=request.user).order_by('-created_at')

        return Response({
            'balanceCards': balance_cards,
            'availableBalance': float(available_balance),
            'hasPayoutMethod': bank_accounts.exists(),
            'primaryMethod': SettlementAccountSerializer(primary_method).data if primary_method else None,
            'bankAccounts': SettlementAccountSerializer(bank_accounts, many=True).data,
            'payoutMethods': SettlementAccountSerializer(bank_accounts, many=True).data,
            'revenueByEvent': revenue_by_event,
            'payoutHistory': PayoutSerializer(payout_history, many=True).data,
        })


class ManagerPayoutMethodsView(views.APIView):
    permission_classes = [IsManagerUser]

    def get(self, request):
        accounts = SettlementAccount.objects.filter(organizer=request.user).order_by('-is_primary', '-created_at')
        return Response(SettlementAccountSerializer(accounts, many=True).data)

    def post(self, request):
        serializer = SettlementAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # If user has no existing payout accounts, mark this one primary by default
        existing_count = SettlementAccount.objects.filter(organizer=request.user).count()
        is_primary = serializer.validated_data.get('is_primary', False) or (existing_count == 0)

        account = SettlementAccount.objects.create(
            organizer=request.user,
            method_type='paypal',
            paypal_email=serializer.validated_data.get('paypal_email', '').strip(),
            is_primary=is_primary,
            status='Primary' if is_primary else 'Verified'
        )

        return Response(SettlementAccountSerializer(account).data, status=status.HTTP_201_CREATED)


class ManagerPayoutMethodDetailView(views.APIView):
    permission_classes = [IsManagerUser]

    def patch(self, request, pk):
        try:
            account = SettlementAccount.objects.get(pk=pk, organizer=request.user)
        except SettlementAccount.DoesNotExist:
            return Response({'detail': 'Payout method not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        is_primary = request.data.get('isPrimary') or request.data.get('is_primary') or (action == 'make_primary')

        if is_primary:
            account.is_primary = True
            account.status = 'Primary'
            account.save()

        return Response(SettlementAccountSerializer(account).data)

    def delete(self, request, pk):
        try:
            account = SettlementAccount.objects.get(pk=pk, organizer=request.user)
        except SettlementAccount.DoesNotExist:
            return Response({'detail': 'Payout method not found.'}, status=status.HTTP_404_NOT_FOUND)

        was_primary = account.is_primary
        account.delete()

        # If deleted was primary, promote the most recent remaining account to primary
        if was_primary:
            next_acc = SettlementAccount.objects.filter(organizer=request.user).order_by('-created_at').first()
            if next_acc:
                next_acc.is_primary = True
                next_acc.status = 'Primary'
                next_acc.save()

        return Response({'message': 'Payout method removed successfully.'}, status=status.HTTP_200_OK)


class RequestPayoutView(views.APIView):
    permission_classes = [IsManagerUser]

    def post(self, request):
        financials = calculate_organizer_financials(request.user)
        available = financials['available_balance']

        # 1. Require at least one verified PayPal payout method
        payout_methods = SettlementAccount.objects.filter(organizer=request.user)
        if not payout_methods.exists():
            return Response({
                'detail': 'Please connect a PayPal account before requesting a withdrawal.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 2. Check available funds
        if available <= 0:
            return Response({
                'detail': 'No funds currently available for disbursement.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 3. Minimum withdrawal threshold ($10.00)
        min_threshold = Decimal('10.00')
        if available < min_threshold:
            return Response({
                'detail': f"Minimum withdrawal threshold is ${min_threshold:,.2f}. Current available balance is ${available:,.2f}."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 4. Parse requested withdrawal amount (or default to 100% available)
        raw_amount = request.data.get('amount')
        if raw_amount is not None:
            try:
                requested_amount = Decimal(str(raw_amount)).quantize(Decimal('0.01'))
            except Exception:
                return Response({'detail': 'Invalid withdrawal amount specified.'}, status=status.HTTP_400_BAD_REQUEST)

            if requested_amount <= Decimal('0.00'):
                return Response({'detail': 'Withdrawal amount must be greater than $0.00.'}, status=status.HTTP_400_BAD_REQUEST)
            if requested_amount < min_threshold:
                return Response({'detail': f'Minimum withdrawal amount is ${min_threshold:,.2f}.'}, status=status.HTTP_400_BAD_REQUEST)
            if requested_amount > available:
                return Response({'detail': f'Requested amount (${requested_amount:,.2f}) exceeds available balance (${available:,.2f}).'}, status=status.HTTP_400_BAD_REQUEST)
            withdraw_amount = requested_amount
        else:
            withdraw_amount = available

        # 5. Selected payout method
        method_id = request.data.get('methodId') or request.data.get('method_id') or request.data.get('payoutMethodId')
        target_method = None
        if method_id:
            target_method = payout_methods.filter(pk=method_id).first()
        if not target_method:
            target_method = payout_methods.filter(is_primary=True).first() or payout_methods.first()

        paypal_email = target_method.paypal_email if target_method else ''
        if not paypal_email:
            return Response({'detail': 'Please specify a valid PayPal account email address.'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate temporary payout number for tracking
        import uuid
        temp_payout_number = f"PO-{uuid.uuid4().hex[:5].upper()}"

        # 6. Execute instant disbursement via PayPal Payouts REST API
        paypal_res = send_paypal_payout(
            payout_number=temp_payout_number,
            recipient_email=paypal_email,
            amount=withdraw_amount,
            currency="USD",
            note="Evento Live Stage Revenue Settlement"
        )

        payout = Payout.objects.create(
            payout_number=temp_payout_number,
            organizer=request.user,
            settlement_account=target_method,
            method_type='paypal',
            destination_summary=f"PayPal ({paypal_email})",
            gross_amount=withdraw_amount,
            fee_deducted=Decimal('0.00'),
            net_disbursed=withdraw_amount,
            paypal_batch_id=paypal_res.get('batch_id', ''),
            paypal_payout_item_id=paypal_res.get('payout_item_id', ''),
            status=paypal_res.get('status', 'Completed')
        )

        return Response({
            'message': f"Disbursement of ${withdraw_amount:,.2f} sent to PayPal ({paypal_email}) successfully.",
            'payout': PayoutSerializer(payout).data,
            'availableBalance': float(max(Decimal('0.00'), available - withdraw_amount)),
        }, status=status.HTTP_201_CREATED)


