import secrets
import uuid

from django.conf import settings
from django.db import models

from user.models import Customer, SellerProfile, hash_secret_token

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion


def generate_order_code():
    return "BM-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


class DeliveryZone(models.Model):

    name = models.CharField(max_length=100, unique=True)  # e.g. "Hossaina center"
    fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.fee})"


class Order(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending confirmation"  # waiting for Bami call
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Seller preparing"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Delivery failed"

    class PaymentMethod(models.TextChoices):
        COD = "cod", "Cash on delivery"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=12, unique=True, default=generate_order_code)
    tracking_token_hash = models.CharField(max_length=64, unique=True)

    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    # Set ONLY when the order was placed while logged in.
    # Unverified accounts see just the orders they placed themselves.
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="placed_orders",
    )

    # Snapshot: what the customer typed at checkout. Never changes later.
    customer_name = models.CharField(max_length=150, blank=True)
    customer_phone = models.CharField(max_length=13, db_index=True)
    delivery_phone = models.CharField(max_length=13)
    town = models.CharField(max_length=100)
    area = models.CharField(max_length=150, blank=True)
    landmark = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    delivery_note = models.TextField(blank=True)
    zone = models.ForeignKey(DeliveryZone, on_delete=models.SET_NULL, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD,
    )

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    needs_confirmation_call = models.BooleanField(default=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_orders",
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    device_id = models.CharField(max_length=100, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    @staticmethod
    def new_tracking_token():
        """Returns (raw_token, hash). Show raw once, store only the hash."""
        raw = secrets.token_urlsafe(24)
        return raw, hash_secret_token(raw)


class OrderItem(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready for pickup"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
    )

    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
    )

    # Snapshot, so later price or name edits never change old orders
    product_name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"


class OrderStatusHistory(models.Model):

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]