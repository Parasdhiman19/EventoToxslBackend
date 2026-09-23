import base64
import requests
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

# In-memory token cache (token, expires_at)
_token_cache = {
    'token': None,
    'expires_at': None
}

def get_paypal_base_url():
    mode = getattr(settings, 'PAYPAL_MODE', 'sandbox')
    if mode == 'live':
        return 'https://api-m.paypal.com'
    return 'https://api-m.sandbox.paypal.com'


def get_paypal_access_token():
    """
    Fetch OAuth2 Bearer token using client_id and client_secret with caching.
    """
    client_id = getattr(settings, 'PAYPAL_CLIENT_ID', '')
    client_secret = getattr(settings, 'PAYPAL_CLIENT_SECRET', '')

    if not client_id or not client_secret:
        logger.warning("PayPal Client ID or Secret is missing in settings.")
        return None

    now = timezone.now()
    if _token_cache['token'] and _token_cache['expires_at'] and now < _token_cache['expires_at']:
        return _token_cache['token']

    url = f"{get_paypal_base_url()}/v1/oauth2/token"
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {'grant_type': 'client_credentials'}

    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        res_data = response.json()
        token = res_data.get('access_token')
        expires_in = res_data.get('expires_in', 3600)
        
        _token_cache['token'] = token
        _token_cache['expires_at'] = now + timedelta(seconds=max(0, expires_in - 60))
        return token
    except Exception as e:
        logger.error(f"Error obtaining PayPal access token: {e}")
        return None


def create_paypal_order(amount, currency="USD", custom_id="", description="Evento Ticket Purchase"):
    """
    Create an order in PayPal with intent=CAPTURE.
    """
    token = get_paypal_access_token()
    if not token:
        # If credentials are not set or failed, raise clean exception
        raise ValueError("Could not authenticate with PayPal Sandbox. Please verify PayPal credentials.")

    url = f"{get_paypal_base_url()}/v2/checkout/orders"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    # Format amount to 2 decimal places string
    formatted_amount = f"{float(amount):.2f}"

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": str(custom_id) if custom_id else "default",
                "custom_id": str(custom_id) if custom_id else "",
                "description": description[:127],
                "amount": {
                    "currency_code": currency,
                    "value": formatted_amount
                }
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload, timeout=12)
    response.raise_for_status()
    return response.json()


def capture_paypal_order(paypal_order_id):
    """
    Capture the payment for an approved PayPal order.
    """
    token = get_paypal_access_token()
    if not token:
        raise ValueError("Could not authenticate with PayPal Sandbox.")

    url = f"{get_paypal_base_url()}/v2/checkout/orders/{paypal_order_id}/capture"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    response = requests.post(url, headers=headers, json={}, timeout=15)
    response.raise_for_status()
    return response.json()
