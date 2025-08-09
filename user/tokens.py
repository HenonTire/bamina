from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from .helper import get_tokens_for_user
from .models import Shop, User  # make sure your User model is imported


class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        shope_id = kwargs.get('shope_id')
        shop = get_object_or_404(Shop, shope_id=shope_id)

        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.user

        if getattr(user, "shop_id", None) != shop.id:
            return Response({'detail': 'User does not belong to this shop.'}, status=status.HTTP_403_FORBIDDEN)

        stay_logged_in = request.data.get("stay_logged_in", False)
        stay_logged_in = str(stay_logged_in).lower() == "true"

        tokens = get_tokens_for_user(user, stay_logged_in)

        response = Response({'access': tokens.get("access", "")}, status=status.HTTP_200_OK)
        response.set_cookie(
            key='refresh_token',
            value=tokens.get("refresh", ""),
            httponly=True,
            secure=True,
            samesite='None',
            max_age=7 * 24 * 60 * 60 if stay_logged_in else 24 * 60 * 60,
        )
        return response


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        shope_id = kwargs.get('shope_id')
        shop = get_object_or_404(Shop, shope_id=shope_id)

        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({'detail': 'Refresh token cookie not found.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(refresh_token)
            user_id = refresh['user_id']  # extract user_id from token
            user = get_object_or_404(User, id=user_id)

            if getattr(user, "shop_id", None) != shop.id:
                return Response({'detail': 'User does not belong to this shop.'}, status=status.HTTP_403_FORBIDDEN)

        except Exception:
            return Response({'detail': 'Invalid refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Run the normal refresh serializer logic
        data = {'refresh': refresh_token}
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)
