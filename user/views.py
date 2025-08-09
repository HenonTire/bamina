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
# 2. Custom Login View
# ------------------------
class CustomTokenObtainView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, shope_id):
        username_or_email = request.data.get('username')
        password = request.data.get('password')

        try:
            shop = Shop.objects.get(shope_id=shope_id)
        except Shop.DoesNotExist:
            return Response({'detail': 'Invalid shop ID'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username_or_email, password=password)
        if not user:
            try:
                user_obj = User.objects.get(email=username_or_email, shop=shop)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass

        if user and hasattr(user, 'shop') and user.shop == shop:
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            res = Response({
                'access': str(access_token),
            }, status=status.HTTP_200_OK)

            return set_refresh_cookie(res, refresh)

        return Response({'detail': 'Invalid credentials or shop'}, status=status.HTTP_401_UNAUTHORIZED)


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
    

class CustomTokenRefreshView(TokenRefreshView):
    """
    Refresh the access token using the refresh token stored in HttpOnly cookies.
    """
    # serializer_class = CookieTokenRefreshSerializer
    parmission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        # Get refresh token from cookies instead of request body
        refresh_token = request.COOKIES.get('refresh')

        if not refresh_token:
            return Response({'detail': 'Refresh token not provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Validate and create new access token
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)

            # Optionally rotate refresh token
            new_refresh = str(refresh)  # Keep same if you don't rotate
            # If rotating: refresh.set_jti(), refresh.set_exp() then save

            response = Response({'access': access_token}, status=status.HTTP_200_OK)

            # Set (or re-set) refresh token cookie
            response.set_cookie(
                key='refresh',
                value=new_refresh,
                httponly=True,
                secure=True,     # Change to False for local dev if needed
                samesite='Lax',  # Or 'Strict'
                max_age=60 * 60 * 24 * 60 # 60 days
            )
            return response

        except Exception:
            return Response({'detail': 'Invalid or expired refresh token'}, status=status.HTTP_401_UNAUTHORIZED)