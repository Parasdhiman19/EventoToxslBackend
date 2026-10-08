import os
from rest_framework_simplejwt.tokens import RefreshToken

COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def set_refresh_cookie(response, refresh_token):
    from django.conf import settings
    is_prod = not getattr(settings, 'DEBUG', True) or os.environ.get('RENDER') == 'true' or os.environ.get('RENDER_EXTERNAL_HOSTNAME') is not None
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        samesite='None' if is_prod else 'Lax',
        secure=is_prod,
        max_age=COOKIE_MAX_AGE,
        path='/',
    )
