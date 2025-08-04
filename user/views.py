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
# user/views.py
from manager.models import Shop  # import your shop model

class Registerview(CreateAPIView):
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        shope_id = kwargs.get('shope_id')
        try:
            shop = Shop.objects.get(shope_id=shope_id)
        except Shop.DoesNotExist:
            return Response({"error": "Invalid shop ID"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(shop=shop)

        refresh = RefreshToken.for_user(user)
        return Response({
            'id': user.id,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

class CustomTokenObtainView(APIView):
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

        if user and user.shop == shop:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        return Response({'detail': 'Invalid credentials or shop'}, status=status.HTTP_401_UNAUTHORIZED)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)




class GoogleLoginView(APIView):
    def post(self, request):
        token = request.data.get('token')
        access_token = request.data.get('access_token')

        if not token:
            return Response({'error': 'Google ID token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), settings.GOOGLE_CLIENT_ID)
            email = idinfo.get('email')
            name = idinfo.get('name')

            # Try to get existing user
            try:
                user = User.objects.get(email=email)
                created = False
            except User.DoesNotExist:
                # If not exists, create with serializer
                user_data = {
                    'email': email,
                    'username': email,  # or use a generated unique username
                }

                serializer = UserSerializer(data=user_data)
                serializer.is_valid(raise_exception=True)
                user = serializer.save()
                created = True

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'created': created,
                'google_access_token': access_token
            })

        except Exception as e:
            return Response({'error': 'Invalid Google token', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)
 

class UpdateUserView(RetrieveUpdateDestroyAPIView):

    serializer_class = UserSerializer
    queryset = User.objects.all()
    lookup_field = 'pk'
    # def get_object(self):
    #     return self.request.user  # Only allow update of the current user

    def patch(self, request, *args, **kwargs):
        # For partial update, call update with partial=True
        return self.partial_update(request, *args, **kwargs)    