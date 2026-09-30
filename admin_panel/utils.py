import logging
from .models import AuditLog

logger = logging.getLogger(__name__)


def log_admin_action(request, action_type, target_model="", target_id="", description="", changes=None):
    """
    Utility helper to reliably record an administrative action in the AuditLog.
    """
    try:
        actor = getattr(request, 'user', None) if request else None
        ip_address = ''
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR', '')

        AuditLog.objects.create(
            actor=actor if (actor and actor.is_authenticated) else None,
            action_type=action_type,
            target_model=target_model,
            target_id=str(target_id),
            description=description,
            changes_payload=changes or {},
            ip_address=ip_address[:45]
        )
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
