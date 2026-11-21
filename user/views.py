from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from . import services, telegram
from .models import Customer, DeviceSession, SellerProfile
from .serializers import (
    CustomerProfileSerializer,
    PhoneValidationMixin,
    SellerProfileSerializer,
    UserProfileSerializer,
)


# =========================================================
# HELPERS
# =========================================================

def client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")  # Render is behind a proxy
    ip = fwd.split(",")[-1].strip() if fwd else request.META.get("REMOTE_ADDR")
    return ip or None


def user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")


def run(fn, *args, **kwargs):
    try:
        return Response(fn(*args, **kwargs) or {"ok": True})
    except services.AuthError as exc:
        return Response({"detail": exc.message}, status=exc.status)


class Public(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []


# =========================================================
# REGISTER / LOGIN
# =========================================================

class RegisterSerializer(PhoneValidationMixin, serializers.Serializer):

    phone = serializers.CharField()
    password = serializers.CharField(min_length=6, write_only=True)
    name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    account_type = serializers.ChoiceField(choices=["buyer", "seller"], default="buyer")
    business_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def validate_password(self, value):
        validate_password(value)  # blocks things like "123456"
        return value


class RegisterView(Public):
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        response = run(
            services.register,
            d["phone"],
            d["password"],
            d["name"],
            d["account_type"],
            d["business_name"],
            client_ip(request) or "",
            user_agent(request),
        )

        if response.status_code == 200:
            response.status_code = 201

        return response


class LoginView(Public):
    throttle_scope = "login"

    def post(self, request):
        return run(
            services.login,
            request.data.get("phone", ""),
            request.data.get("password", ""),
            client_ip(request) or "",
            user_agent(request),
        )


class LogoutView(APIView):

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh", ""))
            DeviceSession.objects.filter(
                jti=str(token["jti"]),
                user=request.user,
            ).update(is_revoked=True)
            token.blacklist()
        except TokenError:
            pass

        return Response(status=204)


class MeView(APIView):

    def get(self, request):
        user = request.user
        data = {"user": UserProfileSerializer(user).data}

        customer = Customer.objects.filter(user=user).first()
        if customer:
            data["customer"] = CustomerProfileSerializer(customer).data

        seller = SellerProfile.objects.filter(user=user).first()
        if seller:
            data["seller"] = SellerProfileSerializer(seller).data

        return Response(data)


# =========================================================
# OPTIONAL TELEGRAM LINK (logged-in users)
# =========================================================

class TelegramLinkStartView(APIView):

    def post(self, request):
        raw = services.start_link(request.user, client_ip(request))

        return Response(
            {
                "token": raw,
                "telegram_url": f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={raw}",
                "expires_in": 600,
            },
            status=201,
        )


class TelegramLinkCompleteView(APIView):
    throttle_scope = "link_poll"

    def post(self, request):
        return run(services.complete_link, request.user, request.data.get("token", ""))


class TelegramWebhookView(Public):

    def post(self, request):
        if not telegram.secret_ok(request.META.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN")):
            return Response(status=403)

        telegram.handle_update(request.data)

        return Response({"ok": True})  # always 200 so Telegram doesn't retry


# =========================================================
# PASSWORD RESET
# =========================================================

class ResetRequestView(Public):
    throttle_scope = "reset"

    def post(self, request):
        services.request_reset(request.data.get("phone", ""))

        return Response(
            {"detail": "If this number is linked to Telegram, a code was sent there."}
        )


class ResetConfirmView(Public):
    throttle_scope = "reset"

    def post(self, request):
        new_password = request.data.get("new_password", "")

        try:
            validate_password(new_password)
        except DjangoValidationError as exc:
            return Response({"detail": list(exc.messages)}, status=400)

        return run(
            services.confirm_reset,
            request.data.get("phone", ""),
            request.data.get("code", ""),
            new_password,
        )