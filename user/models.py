from django.db import models

# Create your models here.
import hashlib
import hmac
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


# =========================================================
# PHONE UTILITIES
# =========================================================

def normalize_ethiopian_phone(phone):
    """
    Normalize Ethiopian mobile numbers to +2519XXXXXXXX
    or +2517XXXXXXXX.
    """

    phone = str(phone).strip().replace(" ", "").replace("-", "")

    if phone.startswith("09") or phone.startswith("07"):
        phone = "+251" + phone[1:]

    elif phone.startswith("9") or phone.startswith("7"):
        phone = "+251" + phone

    elif phone.startswith("251"):
        phone = "+" + phone

    if not phone.startswith("+251"):
        raise ValueError("Only Ethiopian phone numbers are supported.")

    digits = phone[1:]

    if len(digits) != 12 or not digits.isdigit():
        raise ValueError("Invalid Ethiopian phone number.")

    if digits[3] not in ("7", "9"):
        raise ValueError("Invalid Ethiopian mobile number.")

    return phone


def hash_secret_token(token):
    """
    Deterministic HMAC hash for secure token lookup.
    """

    return hmac.new(
        settings.SECRET_KEY.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


# =========================================================
# CUSTOM USER MANAGER
# =========================================================

class UserManager(BaseUserManager):

    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):

        if not phone:
            raise ValueError("Phone number is required.")

        phone = normalize_ethiopian_phone(phone)

        user = self.model(
            phone=phone,
            **extra_fields,
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)

        return user

    def create_superuser(self, phone, password=None, **extra_fields):

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(
            phone,
            password,
            **extra_fields,
        )


# =========================================================
# USER
# =========================================================

class User(AbstractUser):

    username = None

    phone = models.CharField(
        max_length=13,
        unique=True,
    )

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        self.phone = normalize_ethiopian_phone(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.phone


# =========================================================
# CUSTOMER
# =========================================================

class Customer(models.Model):

    class TrustLevel(models.TextChoices):
        NEW = "new", "New"
        VERIFIED = "verified", "Verified"
        REPEAT = "repeat", "Repeat Customer"

    class VerificationMethod(models.TextChoices):
        NONE = "none", "Not Verified"
        TELEGRAM = "telegram", "Telegram"
        MANUAL = "manual", "Manual"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
        null=True,
        blank=True,
    )

    phone = models.CharField(
        max_length=13,
        unique=True,
    )

    name = models.CharField(
        max_length=150,
        blank=True,
    )

    telegram_chat_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    is_verified = models.BooleanField(default=False)

    verification_method = models.CharField(
        max_length=20,
        choices=VerificationMethod.choices,
        default=VerificationMethod.NONE,
    )

    is_blocked = models.BooleanField(default=False)

    trust_level = models.CharField(
        max_length=20,
        choices=TrustLevel.choices,
        default=TrustLevel.NEW,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.phone


# =========================================================
# TELEGRAM VERIFICATION
# =========================================================

class TelegramVerificationChallenge(models.Model):

    class Purpose(models.TextChoices):
        BUYER = "buyer", "Buyer Verification"
        SELLER = "seller", "Seller Verification"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    phone = models.CharField(max_length=13)

    token_hash = models.CharField(
        max_length=64,
        unique=True,
    )

    purpose = models.CharField(
        max_length=20,
        choices=Purpose.choices,
    )

    expires_at = models.DateTimeField()

    is_used = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.phone} - {self.purpose}"


# =========================================================
# SELLER PROFILE
# =========================================================

class SellerProfile(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile",
    )

    phone = models.CharField(
        max_length=13,
        unique=True,
    )

    business_name = models.CharField(max_length=200)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    is_phone_verified = models.BooleanField(default=False)

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.business_name


# =========================================================
# CUSTOMER ADDRESS
# =========================================================

class Address(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="addresses",
    )

    town = models.CharField(max_length=100)

    area = models.CharField(max_length=150, blank=True)

    kebele = models.CharField(max_length=100, blank=True)

    landmark = models.CharField(max_length=255)

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )

    delivery_phone = models.CharField(max_length=13)

    delivery_note = models.TextField(blank=True)

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.phone} - {self.town}"


# =========================================================
# GUEST CART
# =========================================================

class GuestCart(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    token_hash = models.CharField(
        max_length=64,
        unique=True,
    )

    items = models.JSONField(default=list)

    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_expired(self):
        return timezone.now() >= self.expires_at


# =========================================================
# DEVICE SESSIONS
# =========================================================

class DeviceSession(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_sessions",
    )

    jti = models.CharField(
        max_length=255,
        unique=True,
    )

    device_name = models.CharField(max_length=150, blank=True)

    device_type = models.CharField(max_length=50, blank=True)

    last_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    is_revoked = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    last_active = models.DateTimeField(
        default=timezone.now,
    )

    expires_at = models.DateTimeField()

    def __str__(self):
        return f"{self.user.phone} - {self.device_name}"