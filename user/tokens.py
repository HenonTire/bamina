from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.response import Response
from rest_framework import status

from .helper import get_tokens_for_user


class CustomTokenObtainPairView(TokenObtainPairView):

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.user
        stay_logged_in = request.data.get("stay_logged_in", False)
        stay_logged_in = str(stay_logged_in).lower() == "true"

        tokens = get_tokens_for_user(user, stay_logged_in)

        response_data = {
            'access': tokens.get("access", ""),
        }

        response = Response(response_data, status=status.HTTP_200_OK)

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
        refresh_token = request.COOKIES.get('refresh_token')

        if refresh_token is None:
            return Response({'detail': 'Refresh token cookie not found.'}, status=status.HTTP_401_UNAUTHORIZED)

        data = {'refresh': refresh_token}

        serializer = self.get_serializer(data=data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response({'detail': 'Invalid refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)
