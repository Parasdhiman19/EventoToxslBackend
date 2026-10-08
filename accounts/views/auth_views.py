import os
from rest_framework import status, views, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from accounts.serializers import UserSerializer, SignupSerializer, LoginSerializer
from .cookie_utils import get_tokens_for_user, set_refresh_cookie


class SignupView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            tokens = get_tokens_for_user(user)

            response = Response({
                'user': UserSerializer(user).data,
                'access': tokens['access'],
                'message': 'Account created successfully.'
            }, status=status.HTTP_201_CREATED)

            # Store refresh token exclusively in HttpOnly cookie
            set_refresh_cookie(response, tokens['refresh'])
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = get_tokens_for_user(user)

            response = Response({
                'user': UserSerializer(user).data,
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'message': 'Logged in successfully.'
            }, status=status.HTTP_200_OK)

            # Store refresh token in HttpOnly cookie
            set_refresh_cookie(response, tokens['refresh'])
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenRefreshView(views.APIView):
    """
    Reads the refresh token from HttpOnly cookie OR request body and returns a fresh access token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from django.conf import settings
        is_prod = not getattr(settings, 'DEBUG', True) or os.environ.get('RENDER') == 'true' or os.environ.get('RENDER_EXTERNAL_HOSTNAME') is not None

        refresh_token = (
            request.COOKIES.get('refresh_token') or 
            request.data.get('refresh') or 
            request.data.get('refreshToken') or
            request.data.get('refresh_token')
        )

        if not refresh_token:
            return Response(
                {'detail': 'Authentication refresh token not found.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)
            new_refresh_token = str(refresh)

            response = Response({
                'access': new_access_token,
                'refresh': new_refresh_token,
            }, status=status.HTTP_200_OK)
            set_refresh_cookie(response, new_refresh_token)
            return response
        except (TokenError, InvalidToken):
            response = Response(
                {'detail': 'Refresh token is invalid or expired.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
            response.delete_cookie(
                'refresh_token',
                path='/',
                samesite='None' if is_prod else 'Lax',
            )
            return response


class LogoutView(views.APIView):
    """
    Clears the HttpOnly refresh token cookie on the backend.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from django.conf import settings
        is_prod = not getattr(settings, 'DEBUG', True) or os.environ.get('RENDER') == 'true' or os.environ.get('RENDER_EXTERNAL_HOSTNAME') is not None
        response = Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        response.delete_cookie(
            'refresh_token',
            path='/',
            samesite='None' if is_prod else 'Lax',
        )
        return response
