import os
import logging
from django.utils import timezone
import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)


def upload_image_to_cloudinary(file_or_data, folder='evento/banners'):
    """
    Uploads a raw File object or binary file stream directly to Cloudinary.
    Returns the secure HTTPS CDN URL.
    """
    if not file_or_data:
        return ''

    # If it's already an absolute URL, keep it
    if isinstance(file_or_data, str) and file_or_data.startswith(('http://', 'https://')):
        return file_or_data

    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')

    if cloud_name and api_key and api_secret:
        try:
            # Upload directly to Cloudinary with automatic WebP compression
            upload_result = cloudinary.uploader.upload(
                file_or_data,
                folder=folder,
                resource_type='image',
                transformation=[
                    {'quality': 'auto', 'fetch_format': 'auto'}
                ]
            )
            secure_url = upload_result.get('secure_url')
            if secure_url:
                return secure_url
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {e}")

    return ''


def extract_cloudinary_public_id(url):
    """
    Extracts Cloudinary public_id from an HTTPS Cloudinary URL, string, or FieldFile.
    Example:
    'https://res.cloudinary.com/dx8illfsf/image/upload/v1790227617/evento/banners/xyz.jpg'
    -> 'evento/banners/xyz'
    """
    if not url:
        return None

    if hasattr(url, 'name') and url.name:
        url = str(url.name)
    elif not isinstance(url, str):
        url = str(url)

    url = url.strip()
    if not url:
        return None

    if url.startswith('evento/'):
        return url.rsplit('.', 1)[0]

    if 'cloudinary.com' not in url and 'evento/' not in url:
        return None

    try:
        import re
        # Check if url contains an explicit evento/ folder path
        evento_match = re.search(r'(evento/[^.\?#]+)', url)
        if evento_match:
            return evento_match.group(1)

        pattern = r'/image/upload/(?:[a-zA-Z0-9_,-]+/)*(?:v\d+/)?(.+?)(?:\.[a-zA-Z0-9]+)?(?:\?.*)?$'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    except Exception:
        return None
    return None


def delete_image_from_cloudinary(url_or_public_id):
    """
    Deletes an asset from Cloudinary by URL or public_id.
    """
    if not url_or_public_id:
        return False

    public_id = (
        extract_cloudinary_public_id(url_or_public_id)
        if isinstance(url_or_public_id, str) and ('http://' in url_or_public_id or 'https://' in url_or_public_id)
        else url_or_public_id
    )

    if not public_id:
        return False

    try:
        res = cloudinary.uploader.destroy(public_id)
        return res.get('result') in ['ok', 'not found']
    except Exception as e:
        logger.error(f"Failed to delete Cloudinary asset {public_id}: {e}")
        return False





def resolve_image_url(image_field, request=None):
    """
    Resolves a model ImageField (or relative path/URL) to an absolute URL.
    Falls back to /media/events/banners/emptybanner.jpg if no image is provided.
    """
    default_empty_path = '/media/events/banners/emptybanner.jpg'

    if not image_field:
        if request:
            return request.build_absolute_uri(default_empty_path)
        return f"http://127.0.0.1:8000{default_empty_path}"

    # 1. Extract string value from FieldFile or str
    image_str = ''
    if hasattr(image_field, 'name') and image_field.name:
        image_str = str(image_field.name).strip()
    elif isinstance(image_field, str):
        image_str = image_field.strip()
    else:
        image_str = str(image_field).strip()

    if not image_str:
        if request:
            return request.build_absolute_uri(default_empty_path)
        return f"http://127.0.0.1:8000{default_empty_path}"

    # 2. If it is already an absolute Cloudinary / HTTPS URL or data URI, return as-is
    if image_str.startswith(('http://', 'https://', 'data:')):
        return image_str

    # 3. If it's a Django FieldFile instance pointing to local storage
    if hasattr(image_field, 'url'):
        try:
            url = image_field.url
            if url:
                if url.startswith(('http://', 'https://')):
                    return url
                if request:
                    return request.build_absolute_uri(url)
                return f"http://127.0.0.1:8000{url}"
        except (ValueError, Exception):
            pass

    if not image_str.startswith('/media/') and not image_str.startswith('/'):
        image_str = f"/media/{image_str}"
    if image_str.startswith('/media/'):
        if request:
            return request.build_absolute_uri(image_str)
        return f"http://127.0.0.1:8000{image_str}"
    return image_str



def format_relative_time(dt):
    """
    Formats a datetime object to human readable relative time (e.g. '5m ago', '2d ago').
    """
    if not dt:
        return ''
    now = timezone.now()
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 0:
        return 'Just now'
    if seconds < 60:
        return 'Just now'
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 7:
        return f"{days}d ago"
    return dt.strftime('%b %d, %Y')
