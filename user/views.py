from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.timezone import now
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError
from .helper import set_refresh_cookie
from .models import Shop
from django.shortcuts import render
from django.contrib.auth import get_user_model
from .serializer import PasswordResetConfirmSerializer, PasswordResetRequestSerializer, UserSerializer
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

    def post(self, request, *args, **kwargs):
        token = request.data.get('token')
        access_token_google = request.data.get('access_token')
        shope_id = kwargs.get('shope_id')

        if not token:
            return Response({'error': 'Google ID token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            shop = Shop.objects.get(shope_id=shope_id)
        except Shop.DoesNotExist:
            return Response({'error': 'Invalid shop ID'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify Google token
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )

            email = idinfo.get('email')
            name = idinfo.get('name')

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
                user = serializer.save(shop=shop)
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
        if not user.shop or str(user.shop.shope_id) != str(shope_id):
            raise ValidationError(
                "You do not have permission to update this user.")
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
            # requires SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"] = True and app installed
            token.blacklist()
        except TokenError:
            return Response({'detail': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

        # Create empty response and delete cookie
        response = Response(
            {'detail': 'Logged out successfully'}, status=status.HTTP_200_OK)
        response.delete_cookie('refresh')
        return response


# Password Reset Views
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                success=False,
                message="Failed to send email",
                errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "User with this email does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = PasswordResetTokenGenerator().make_token(user)

        reset_link = f"http://localhost:3000/reset-password?uidb64={uidb64}&token={token}"

        subject = "Reset Your Password – Bamina Online Shopping Store"
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = user.email

        html_content = render_to_string("emails/password_reset_email.html", {
            "user_name": user.username or user.email,
            "reset_link": reset_link,
            "current_year": now().year,
        })

        email = EmailMultiAlternatives(subject, "", from_email, [to_email])
        email.attach_alternative(html_content, "text/html")
        email.send()

        return Response({"message": "Password reset link sent."}, status=status.HTTP_200_OK)


password_reset_request_view = PasswordResetRequestView.as_view()


class PasswordResetConfirmView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                success=False,
                message="Failed to confirm password",
                errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer.save()
        return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)


class UserDetailView(APIView):

    def get(self, request, *args, **kwargs):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data)
