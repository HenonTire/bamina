from django.shortcuts import render
from django.contrib.auth import get_user_model
from .serializer import UserSerializer
from rest_framework.generics import CreateAPIView, RetrieveUpdateDestroyAPIView, UpdateAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
User = get_user_model()
from .models import Shop
from .helper import set_refresh_cookie
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError

# ------------------------
# 1. Register View
# ------------------------
class RegisterView(CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    

    def create(self, request, *args, **kwargs):
        shope_id = kwargs.get('shope_id')
        

        try:
            shop = Shop.objects.get(shope_id=shope_id)
        except Shop.DoesNotExist:
            return Response({"error": "Invalid shop ID"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(shop=shop)
        print("DEBUG: type(user) =", type(user), "value =", user)

        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        # stay_logged_in = request.data.get('stay_logged_in', False).lower() == 'true'

        res = Response({
            'id': user.id,
            'access': str(access_token),
        }, status=status.HTTP_201_CREATED)

        return set_refresh_cookie(res, refresh, )




# ------------------------
# 3. Google Login View
# ------------------------
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        token = request.data.get('token')
        access_token_google = request.data.get('access_token')

        if not token:
            return Response({'error': 'Google ID token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify Google token
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )

            email = idinfo.get('email')
            name = idinfo.get('name')

            # Get or create user
            try:
                user = User.objects.get(email=email)
                created = False
            except User.DoesNotExist:
                user_data = {
                    'email': email,
                    'username': name,
                }
                serializer = UserSerializer(data=user_data)
                serializer.is_valid(raise_exception=True)
                user = serializer.save()
                created = True

            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            res = Response({
                'access': str(access_token),
                'created': created,
                'google_access_token': access_token_google
            }, status=status.HTTP_200_OK)

            return set_refresh_cookie(res, refresh)

        except Exception as e:
            return Response({'error': 'Invalid Google token', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UpdateUserView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    queryset = User.objects.all()
    lookup_field = 'pk'
    # def get_object(self):
    #     return self.request.user  # Only allow update of the current user
    def get_object(self):
        shope_id = self.kwargs.get('shope_id')
        user = self.request.user
        if user.shop.shope_id != shope_id:
            raise ValidationError("You do not have permission to update this user.")
        return user
    def patch(self, request, *args, **kwargs):
        # For partial update, call update with partial=True
        return self.partial_update(request, *args, **kwargs)    
    


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        shope_id = kwargs.get('shope_id') 
        refresh_token = request.COOKIES.get('refresh')

        if not refresh_token:
            return Response({'detail': 'No refresh token in cookie'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()  # requires SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"] = True and app installed
        except TokenError:
            return Response({'detail': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

        # Create empty response and delete cookie
        response = Response({'detail': 'Logged out successfully'}, status=status.HTTP_200_OK)
        response.delete_cookie('refresh')
        return response
    

