"""
Evento Notification Service
============================

Central service layer for creating, saving, and delivering notifications.

Design Principles:
- Business logic NEVER calls Notification.objects.create() directly.
- All notification creation goes through NotificationService methods.
- Notification failures are isolated — they never break the calling transaction.
- Actor == Recipient suppression: users don't receive notifications for their own actions.
- WebSocket delivery happens immediately after DB save via Redis channel layer.

Usage Example:
    from notifications.services import NotificationService

    NotificationService.send_ticket_issued(
        order=order,
        ticket=ticket,
        recipient=order.user,
    )
"""

import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .constants import (
    WELCOME, PASSWORD_CHANGED, PASSWORD_RESET_REQUESTED,
    ORDER_PLACED, TICKET_ISSUED, PAYMENT_FAILED,
    EVENT_UPDATED, EVENT_CANCELLED, EVENT_COMMENT_REPLIED,
    TICKET_SOLD, EVENT_SOLD_OUT, EVENT_LOW_INVENTORY,
    EVENT_PUBLISHED, EVENT_COMMENT_RECEIVED,
    PAYOUT_DISBURSED, PAYOUT_FAILED,
    ORGANIZER_PROFILE_ACTIVATED,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Static factory methods for every supported notification type.
    Each method handles: DB creation → unread count refresh → WebSocket push.
    """

    # ─────────────────────────────────────────────────────────────
    # Core Internal Method
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def create_notification(
        recipient,
        notification_type: str,
        title: str,
        message: str,
        data: dict = None,
        actor=None,
        event=None,
        order=None,
        ticket=None,
    ):
        """
        Create and persist a Notification, then push it to the recipient's
        WebSocket connection via Redis channel layer.

        Returns the Notification instance, or None on failure.
        Failures are logged but NEVER re-raised to avoid breaking callers.
        """
        # Suppress self-notifications (actor doing something to themselves)
        if actor and recipient and actor.pk == recipient.pk:
            return None

        try:
            from .models import Notification
            notif = Notification.objects.create(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                message=message,
                data=data or {},
                actor=actor,
                event=event,
                order=order,
                ticket=ticket,
            )

            # Push to WebSocket immediately
            NotificationService._push_to_websocket(notif)
            return notif

        except Exception as exc:
            logger.error(
                f'[NotificationService] Failed to create notification '
                f'type={notification_type} recipient={getattr(recipient, "id", "?")} '
                f'error={exc}',
                exc_info=True
            )
            return None

    @staticmethod
    def _push_to_websocket(notification):
        """
        Serialize the notification and send it to the recipient's personal
        Redis channel group. The NotificationConsumer will forward it to
        the open WebSocket connection(s) for that user.
        """
        try:
            from .serializers import NotificationSerializer
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            group_name = f'notif_user_{notification.recipient_id}'
            unread_count = notification.__class__.objects.filter(
                recipient_id=notification.recipient_id,
                is_read=False
            ).count()

            payload = {
                'type': 'notification.new',  # maps to consumer.notification_new()
                'notification': NotificationSerializer(notification).data,
                'unread_count': unread_count,
            }

            async_to_sync(channel_layer.group_send)(group_name, payload)

        except Exception as exc:
            logger.warning(
                f'[NotificationService] WebSocket push failed for '
                f'notification_id={notification.pk}: {exc}'
            )

    # ─────────────────────────────────────────────────────────────
    # USER — Account & Security Notifications
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def send_welcome(recipient):
        """Sent when a new user completes signup via OTP verification."""
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=WELCOME,
            title='Welcome to Evento! 🎉',
            message=(
                f'Hey {recipient.full_name or "there"}! Your account is ready. '
                'Discover live events, buy tickets, and save your favourites.'
            ),
            data={'action_url': '/'},
        )

    @staticmethod
    def send_password_changed(recipient):
        """Sent when a user successfully changes or resets their password."""
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=PASSWORD_CHANGED,
            title='Password updated',
            message=(
                'Your password was changed successfully. '
                'If you did not make this change, please contact support immediately.'
            ),
            data={'action_url': '/user/profile'},
        )

    @staticmethod
    def send_password_reset_requested(recipient):
        """Sent when a password reset email link is generated."""
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=PASSWORD_RESET_REQUESTED,
            title='Password reset link sent',
            message='A password reset link has been sent to your email address.',
            data={'action_url': '/account/forgot-password'},
        )

    # ─────────────────────────────────────────────────────────────
    # USER — Tickets & Orders
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def send_order_placed(recipient, order):
        """Sent to the buyer when an order is created and confirmed."""
        event = order.event
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=ORDER_PLACED,
            title='Order confirmed',
            message=(
                f'Your order for {event.title} has been confirmed. '
                f'{order.quantity} ticket{"s" if order.quantity != 1 else ""} — '
                f'${order.total_amount:,.2f} total.'
            ),
            data={
                'event_id': event.id,
                'order_id': order.id,
                'order_number': order.order_number,
                'action_url': f'/user/orders',
            },
            event=event,
            order=order,
        )

    @staticmethod
    def send_ticket_issued(recipient, order, ticket=None):
        """Sent to the buyer after tickets are generated and attached to the order."""
        event = order.event
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=TICKET_ISSUED,
            title='Your ticket is ready ✓',
            message=(
                f'Your ticket for {event.title} is ready. '
                f'Show your QR code at the gate on {event.date.strftime("%b %d, %Y")}.'
            ),
            data={
                'event_id': event.id,
                'order_id': order.id,
                'ticket_code': getattr(ticket, 'ticket_code', None),
                'action_url': '/user/tickets',
            },
            event=event,
            order=order,
            ticket=ticket,
        )

    @staticmethod
    def send_payment_failed(recipient, order):
        """Sent to the buyer when a PayPal capture fails."""
        event = order.event
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=PAYMENT_FAILED,
            title='Payment unsuccessful',
            message=(
                f'Your payment for {event.title} could not be completed. '
                'No charge was made. Please try again or use a different payment method.'
            ),
            data={
                'event_id': event.id,
                'order_id': order.id,
                'action_url': f'/events/{event.id}',
            },
            event=event,
            order=order,
        )

    # ─────────────────────────────────────────────────────────────
    # USER — Events (Attendee)
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def send_event_updated(recipient, event, change_summary: str = ''):
        """Sent to all confirmed attendees when an organizer edits event details."""
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=EVENT_UPDATED,
            title=f'Event updated: {event.title}',
            message=(
                f'{event.title} has been updated by the organiser.'
                + (f' {change_summary}' if change_summary else ' Please review the latest details.')
            ),
            data={
                'event_id': event.id,
                'action_url': f'/events/{event.id}',
            },
            event=event,
        )

    @staticmethod
    def send_event_cancelled(recipient, event, actor=None):
        """Sent to all confirmed attendees when an event is cancelled."""
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=EVENT_CANCELLED,
            title=f'Event cancelled: {event.title}',
            message=(
                f'Unfortunately, {event.title} has been cancelled. '
                'Please contact the organiser for refund information.'
            ),
            data={
                'event_id': event.id,
                'action_url': '/user/tickets',
            },
            actor=actor,
            event=event,
        )

    @staticmethod
    def send_comment_replied(recipient, event, actor, parent_comment_id: int):
        """Sent to the author of a comment when someone replies to it."""
        actor_name = actor.full_name or actor.email.split('@')[0].title()
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=EVENT_COMMENT_REPLIED,
            title=f'{actor_name} replied to your comment',
            message=f'{actor_name} replied to your comment on {event.title}.',
            data={
                'event_id': event.id,
                'comment_id': parent_comment_id,
                'action_url': f'/events/{event.id}',
            },
            actor=actor,
            event=event,
        )

    # ─────────────────────────────────────────────────────────────
    # MANAGER — Sales Notifications
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def send_ticket_sold(organizer, order):
        """Sent to the organizer each time a confirmed ticket sale is made."""
        event = order.event
        buyer_name = order.user.full_name or order.user.email.split('@')[0].title()
        return NotificationService.create_notification(
            recipient=organizer,
            notification_type=TICKET_SOLD,
            title=f'{order.quantity} ticket{"s" if order.quantity != 1 else ""} sold',
            message=(
                f'{buyer_name} purchased {order.quantity} ticket'
                f'{"s" if order.quantity != 1 else ""} for {event.title}. '
                f'Revenue: ${order.total_amount:,.2f}.'
            ),
            data={
                'event_id': event.id,
                'order_id': order.id,
                'action_url': f'/manager/tickets',
            },
            actor=order.user,
            event=event,
            order=order,
        )

    @staticmethod
    def send_event_sold_out(organizer, event):
        """Sent to the organizer when all ticket tiers for an event are sold out."""
        return NotificationService.create_notification(
            recipient=organizer,
            notification_type=EVENT_SOLD_OUT,
            title=f'🎟 {event.title} is SOLD OUT',
            message=(
                f'All tickets for {event.title} have been sold. '
                'Congratulations! Consider adding more capacity via the event editor.'
            ),
            data={
                'event_id': event.id,
                'action_url': f'/manager/events/{event.id}',
            },
            event=event,
        )

    @staticmethod
    def send_event_low_inventory(organizer, event, remaining: int):
        """Sent to the organizer when remaining ticket count drops to ≤10%."""
        return NotificationService.create_notification(
            recipient=organizer,
            notification_type=EVENT_LOW_INVENTORY,
            title=f'Low inventory: {event.title}',
            message=(
                f'Only {remaining} ticket{"s" if remaining != 1 else ""} remaining '
                f'for {event.title}. Consider promoting to fill remaining seats.'
            ),
            data={
                'event_id': event.id,
                'remaining': remaining,
                'action_url': f'/manager/events/{event.id}',
            },
            event=event,
        )

    # ─────────────────────────────────────────────────────────────
    # MANAGER — Event Management Notifications
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def send_event_published(organizer, event):
        """Sent to the organizer when their event is first published."""
        return NotificationService.create_notification(
            recipient=organizer,
            notification_type=EVENT_PUBLISHED,
            title=f'Event published: {event.title}',
            message=(
                f'{event.title} is now live and accepting ticket sales. '
                f'Share your event to start selling!'
            ),
            data={
                'event_id': event.id,
                'action_url': f'/manager/events/{event.id}',
            },
            event=event,
        )

    @staticmethod
    def send_event_comment_received(organizer, event, actor):
        """Sent to the organizer when a user posts a comment on their event."""
        # Skip if organizer commented on their own event
        if actor and organizer and actor.pk == organizer.pk:
            return None
        actor_name = actor.full_name or actor.email.split('@')[0].title() if actor else 'Someone'
        return NotificationService.create_notification(
            recipient=organizer,
            notification_type=EVENT_COMMENT_RECEIVED,
            title='New comment on your event',
            message=f'{actor_name} commented on {event.title}.',
            data={
                'event_id': event.id,
                'action_url': f'/manager/events/{event.id}',
            },
            actor=actor,
            event=event,
        )

    # ─────────────────────────────────────────────────────────────
    # MANAGER — Payout Notifications
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def send_payout_disbursed(organizer, payout):
        """Sent to the organizer when a PayPal payout is successfully sent."""
        return NotificationService.create_notification(
            recipient=organizer,
            notification_type=PAYOUT_DISBURSED,
            title='Payout sent ✓',
            message=(
                f'${payout.net_disbursed:,.2f} has been disbursed to '
                f'{payout.destination_summary}. '
                f'Reference: {payout.payout_number}.'
            ),
            data={
                'payout_id': payout.id,
                'payout_number': payout.payout_number,
                'action_url': '/manager/payouts',
            },
        )

    @staticmethod
    def send_payout_failed(organizer, amount, error_message: str = ''):
        """Sent to the organizer when a PayPal payout request fails."""
        return NotificationService.create_notification(
            recipient=organizer,
            notification_type=PAYOUT_FAILED,
            title='Payout failed',
            message=(
                f'Your payout request of ${amount:,.2f} could not be processed. '
                + (error_message or 'Please verify your PayPal account and try again.')
            ),
            data={
                'action_url': '/manager/payouts',
            },
        )

    # ─────────────────────────────────────────────────────────────
    # MANAGER — Account Notifications
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def send_organizer_profile_activated(organizer):
        """Sent when a user successfully activates their organizer/manager profile."""
        org_name = getattr(getattr(organizer, 'organizer_profile', None), 'organization_name', None)
        display = org_name or organizer.full_name or 'your studio'
        return NotificationService.create_notification(
            recipient=organizer,
            notification_type=ORGANIZER_PROFILE_ACTIVATED,
            title='Organizer profile activated 🚀',
            message=(
                f'{display} is now live on Evento! '
                'You can create events, manage attendees, and track sales from your manager console.'
            ),
            data={'action_url': '/manager/overview'},
        )
