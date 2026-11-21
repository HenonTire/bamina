import secrets
from datetime import datetime, timedelta, timezone as dt_tz

from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from . import telegram
from .models import (
    Customer,
    DeviceSession,
    SellerProfile,
    TelegramVerificationChallenge as Challenge,
    User,
    hash_secret_token,
    normalize_ethiopian_phone,
)

TTL = timedelta(minutes=10)
LOCK_AFTER = 5
LOCK_SECONDS = 900
RESET_MAX_PER_HOUR = 5


class AuthError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def issue_tokens(user, ip="", user_agent=""):
    refresh = RefreshToken.for_user(user)

    DeviceSession.objects.create(
        user=user,
        jti=str(refresh["jti"]),
        device_name=user_agent[:150],
        last_ip=ip or None,
        expires_at=datetime.fromtimestamp(refresh["exp"], tz=dt_tz.utc),
    )

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


# =========================================================
# REGISTER / LOGIN  (phone + password, no external app)
# =========================================================

@transaction.atomic
def register(phone, password, name, account_type, business_name, ip="", user_agent=""):
    phone = normalize_ethiopian_phone(phone)

    if User.objects.filter(phone=phone).exists():
        raise AuthError("This phone is already registered. Please log in.", 409)

    if account_type == "seller" and not business_name:
        raise AuthError("business_name is required for sellers.")

    user = User.objects.create_user(phone, password, first_name=name[:150])

    # A guest may already have ordered with this phone: attach, don't duplicate.
    customer, created = Customer.objects.select_for_update().get_or_create(
        phone=phone,
        defaults={"user": user, "name": name},
    )

    if not created:
        customer.user = user
        if name and not customer.name:
            customer.name = name
        customer.save()

    seller = None
    if account_type == "seller":
        seller = SellerProfile.objects.create(
            user=user,
            business_name=business_name,
            status=SellerProfile.Status.PENDING,
        )

    return {
        **issue_tokens(user, ip, user_agent),
        "seller_status": seller.status if seller else None,
    }


def login(phone, password, ip="", user_agent=""):
    try:
        phone = normalize_ethiopian_phone(phone)
    except ValueError:
        raise AuthError("Wrong phone or password.")

    key = f"loginfail:{phone}"

    if cache.get(key, 0) >= LOCK_AFTER:
        raise AuthError("Too many failed attempts. Try again in 15 minutes.", 429)

    user = authenticate(phone=phone, password=password)

    # staff must use the admin login, never the public API
    if not user or not user.is_active or user.is_staff or user.is_superuser:
        cache.set(key, cache.get(key, 0) + 1, LOCK_SECONDS)
        raise AuthError("Wrong phone or password.")

    cache.delete(key)

    return issue_tokens(user, ip, user_agent)


# =========================================================
# OPTIONAL TELEGRAM LINK  (logged-in users)
# =========================================================

def start_link(user, ip=None):
    Challenge.objects.filter(
        phone=user.phone,
        purpose=Challenge.Purpose.LINK,
        is_used=False,
    ).update(is_used=True)

    raw = secrets.token_urlsafe(24)

    Challenge.objects.create(
        phone=user.phone,
        purpose=Challenge.Purpose.LINK,
        token_hash=hash_secret_token(raw),
        expires_at=timezone.now() + TTL,
        ip_address=ip,
    )

    return raw


@transaction.atomic
def complete_link(user, raw):
    ch = (
        Challenge.objects.select_for_update()
        .filter(
            token_hash=hash_secret_token(raw),
            purpose=Challenge.Purpose.LINK,
            phone=user.phone,
        )
        .first()
    )

    if not ch or ch.is_used or ch.is_expired():
        raise AuthError("Invalid or expired link.")

    if not ch.verified_at:
        raise AuthError("Not verified yet.", 409)  # client keeps polling

    ch.is_used = True
    ch.save(update_fields=["is_used"])

    customer, _ = Customer.objects.get_or_create(
        phone=user.phone,
        defaults={"user": user},
    )

    customer.user = customer.user or user
    customer.is_verified = True
    customer.verification_method = Customer.VerificationMethod.TELEGRAM

    chat_taken = (
        Customer.objects.exclude(pk=customer.pk)
        .filter(telegram_chat_id=ch.telegram_chat_id)
        .exists()
    )
    if not chat_taken:
        customer.telegram_chat_id = ch.telegram_chat_id

    customer.save()

    SellerProfile.objects.filter(user=user).update(is_phone_verified=True)


# =========================================================
# PASSWORD RESET  (only for Telegram-linked accounts)
# =========================================================

def request_reset(phone):
    """Always returns silently so attackers can't learn which phones exist."""
    try:
        phone = normalize_ethiopian_phone(phone)
    except ValueError:
        return

    customer = (
        Customer.objects.filter(phone=phone, is_verified=True, user__isnull=False)
        .exclude(telegram_chat_id__isnull=True)
        .first()
    )

    if not customer:
        return

    now = timezone.now()

    recent = Challenge.objects.filter(
        phone=phone,
        purpose=Challenge.Purpose.RESET,
        created_at__gte=now - timedelta(hours=1),
    )
    last = recent.order_by("-created_at").first()

    if recent.count() >= RESET_MAX_PER_HOUR:
        return

    if last and (now - last.created_at).total_seconds() < 60:
        return

    code = f"{secrets.randbelow(10**6):06d}"

    Challenge.objects.create(
        phone=phone,
        purpose=Challenge.Purpose.RESET,
        token_hash=hash_secret_token(f"{phone}:{code}"),
        expires_at=now + TTL,
    )

    telegram.send(
        customer.telegram_chat_id,
        f"Your Bami password reset code is {code}. It expires in 10 minutes.",
    )


@transaction.atomic
def confirm_reset(phone, code, new_password):
    try:
        phone = normalize_ethiopian_phone(phone)
    except ValueError:
        raise AuthError("Invalid or expired code.")

    ch = (
        Challenge.objects.select_for_update()
        .filter(phone=phone, purpose=Challenge.Purpose.RESET, is_used=False)
        .order_by("-created_at")
        .first()
    )

    if not ch or ch.is_expired() or ch.attempts >= telegram.MAX_ATTEMPTS:
        raise AuthError("Invalid or expired code.")

    if ch.token_hash != hash_secret_token(f"{phone}:{code}"):
        ch.attempts += 1
        ch.save(update_fields=["attempts"])
        raise AuthError("Invalid or expired code.")

    user = User.objects.get(phone=phone)
    user.set_password(new_password)
    user.save()

    ch.is_used = True
    ch.save(update_fields=["is_used"])

    # sign out everywhere
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)

    DeviceSession.objects.filter(user=user).update(is_revoked=True)