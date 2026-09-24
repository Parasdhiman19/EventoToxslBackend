import logging
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from events.models import Event
from accounts.models import OrganizerProfile
from events.utils.media_utils import (
    extract_cloudinary_public_id,
    delete_image_from_cloudinary,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event Banner Signals
# ---------------------------------------------------------------------------

@receiver(post_delete, sender=Event)
def cleanup_event_banner_on_delete(sender, instance, **kwargs):
    """
    Deletes the Cloudinary banner artwork when an Event is deleted.
    """
    if instance.banner_image:
        public_id = extract_cloudinary_public_id(instance.banner_image)
        if public_id:
            logger.info(f"Deleting Cloudinary banner {public_id} for deleted Event #{instance.id}")
            delete_image_from_cloudinary(public_id)


@receiver(pre_save, sender=Event)
def cleanup_event_banner_on_change(sender, instance, **kwargs):
    """
    Deletes the old Cloudinary banner artwork when an Event's banner is replaced.
    """
    if not instance.pk:
        return  # Brand new event, no previous image to delete

    try:
        old_instance = Event.objects.filter(pk=instance.pk).first()
        if not old_instance or not old_instance.banner_image:
            return

        old_banner_str = str(old_instance.banner_image).strip()
        new_banner_str = str(instance.banner_image or '').strip()

        # If banner changed to a different image or was cleared
        if old_banner_str and old_banner_str != new_banner_str:
            old_public_id = extract_cloudinary_public_id(old_banner_str)
            new_public_id = extract_cloudinary_public_id(new_banner_str)

            # Avoid deleting if it's the exact same public_id
            if old_public_id and old_public_id != new_public_id:
                logger.info(f"Replacing banner: Deleting old Cloudinary banner {old_public_id} for Event #{instance.id}")
                delete_image_from_cloudinary(old_public_id)
    except Exception as e:
        logger.error(f"Error during Event banner pre_save signal cleanup: {e}")


# ---------------------------------------------------------------------------
# Organizer Profile Logo Signals
# ---------------------------------------------------------------------------

@receiver(post_delete, sender=OrganizerProfile)
def cleanup_organizer_logo_on_delete(sender, instance, **kwargs):
    """
    Deletes the Cloudinary logo asset when an OrganizerProfile is deleted.
    """
    if instance.logo_url:
        public_id = extract_cloudinary_public_id(instance.logo_url)
        if public_id:
            logger.info(f"Deleting Cloudinary logo {public_id} for deleted OrganizerProfile #{instance.id}")
            delete_image_from_cloudinary(public_id)


@receiver(pre_save, sender=OrganizerProfile)
def cleanup_organizer_logo_on_change(sender, instance, **kwargs):
    """
    Deletes the old Cloudinary logo asset when an Organizer's logo is replaced.
    """
    if not instance.pk:
        return

    try:
        old_instance = OrganizerProfile.objects.filter(pk=instance.pk).first()
        if not old_instance or not old_instance.logo_url:
            return

        old_logo_str = str(old_instance.logo_url).strip()
        new_logo_str = str(instance.logo_url or '').strip()

        if old_logo_str and old_logo_str != new_logo_str:
            old_public_id = extract_cloudinary_public_id(old_logo_str)
            new_public_id = extract_cloudinary_public_id(new_logo_str)

            if old_public_id and old_public_id != new_public_id:
                logger.info(f"Replacing logo: Deleting old Cloudinary logo {old_public_id} for OrganizerProfile #{instance.id}")
                delete_image_from_cloudinary(old_public_id)
    except Exception as e:
        logger.error(f"Error during OrganizerProfile logo pre_save signal cleanup: {e}")
