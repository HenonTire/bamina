from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from catalog.models import Product
from user.models import Customer, SellerProfile

from .models import DeliveryZone, Order, OrderItem, OrderStatusHistory

MAX_LINES = 20
MAX_QTY = 20

LIMIT_PHONE_24H = 5
LIMIT_PHONE_PENDING = 3
LIMIT_IP_24H = 10
LIMIT_DEVICE_24H = 5

S = Order.Status

TRANSITIONS = {
    S.PENDING: {S.CONFIRMED, S.CANCELLED},
    S.CONFIRMED: {S.PREPARING, S.CANCELLED},
    S.PREPARING: {S.OUT_FOR_DELIVERY, S.CANCELLED},
    S.OUT_FOR_DELIVERY: {S.DELIVERED, S.FAILED},
    S.DELIVERED: set(),
    S.CANCELLED: set(),
    S.FAILED: set(),
}


class OrderError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


# =========================================================
# ABUSE LIMITS
# =========================================================

def _check_limits(phone, ip, device_id):
    since = timezone.now() - timedelta(hours=24)
    recent = Order.objects.filter(created_at__gte=since)

    if recent.filter(customer_phone=phone).count() >= LIMIT_PHONE_24H:
        raise OrderError("Too many orders from this phone today. Please try tomorrow.", 429)

    pending = Order.objects.filter(customer_phone=phone, status=S.PENDING).count()
    if pending >= LIMIT_PHONE_PENDING:
        raise OrderError(
            "You already have orders waiting for confirmation. Please wait for our call.", 429
        )

    if ip and recent.filter(ip_address=ip).count() >= LIMIT_IP_24H:
        raise OrderError("Too many orders from this connection today.", 429)

    if device_id and recent.filter(device_id=device_id).count() >= LIMIT_DEVICE_24H:
        raise OrderError("Too many orders from this device today.", 429)


# =========================================================
# CREATE ORDER (guest or logged in)
# =========================================================

@transaction.atomic
def create_order(data, user=None, ip=None, device_id=""):
    """
    data: validated dict with name, phone, delivery_phone, town, area, landmark,
          latitude, longitude, delivery_note, zone_id, items=[{product_id, quantity}]
    Returns (order, raw_tracking_token).
    Prices ALWAYS come from the database, never from the client.
    """
    phone = data["phone"]
    delivery_phone = data.get("delivery_phone") or phone

    customer, _ = Customer.objects.select_for_update().get_or_create(
        phone=phone,
        defaults={"name": data["name"]},
    )

    if customer.is_blocked:
        raise OrderError("This number cannot place orders.", 403)

    if not customer.name:
        customer.name = data["name"]
        customer.save(update_fields=["name"])

    _check_limits(phone, ip, device_id)

    # merge duplicate lines
    wanted = {}
    for line in data["items"]:
        pid = line["product_id"]
        wanted[pid] = wanted.get(pid, 0) + line["quantity"]

    if not wanted or len(wanted) > MAX_LINES:
        raise OrderError(f"An order needs between 1 and {MAX_LINES} different products.")

    if any(q > MAX_QTY for q in wanted.values()):
        raise OrderError(f"You can order at most {MAX_QTY} of one product.")

    products = {
        p.id: p
        for p in Product.objects.select_for_update(of=("self",))
        .select_related("seller")
        .filter(
            id__in=wanted.keys(),
            status=Product.Status.ACTIVE,
            seller__status=SellerProfile.Status.APPROVED,
        )
    }

    if len(products) != len(wanted):
        raise OrderError("One or more products are no longer available.", 400)

    zone = None
    if data.get("zone_id"):
        zone = DeliveryZone.objects.filter(id=data["zone_id"], is_active=True).first()
        if not zone:
            raise OrderError("Unknown delivery zone.", 400)

    lines = []
    subtotal = Decimal("0")

    for pid, qty in wanted.items():
        product = products[pid]

        if product.stock is not None:
            if product.stock < qty:
                raise OrderError(f"Only {product.stock} left of {product.name}.", 409)
            product.stock -= qty
            product.save(update_fields=["stock"])

        line_total = product.price * qty
        subtotal += line_total
        lines.append((product, qty, line_total))

    delivery_fee = zone.fee if zone else Decimal("0")

    raw_token, token_hash = Order.new_tracking_token()

    order = Order.objects.create(
        tracking_token_hash=token_hash,
        customer=customer,
        placed_by=user if (user is not None and user.is_authenticated) else None,
        customer_name=data["name"],
        customer_phone=phone,
        delivery_phone=delivery_phone,
        town=data["town"],
        area=data.get("area", ""),
        landmark=data["landmark"],
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        delivery_note=data.get("delivery_note", ""),
        zone=zone,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=subtotal + delivery_fee,
        needs_confirmation_call=customer.trust_level == Customer.TrustLevel.NEW,
        ip_address=ip,
        device_id=device_id,
    )

    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product=product,
                seller=product.seller,
                product_name=product.name,
                unit_price=product.price,
                quantity=qty,
                line_total=line_total,
            )
            for product, qty, line_total in lines
        ]
    )

    OrderStatusHistory.objects.create(
        order=order,
        from_status="",
        to_status=S.PENDING,
        note="Order placed",
    )

    return order, raw_token


# =========================================================
# STATUS CHANGES
# =========================================================

@transaction.atomic
def change_status(order, to_status, by=None, note=""):
    order = Order.objects.select_for_update().get(pk=order.pk)

    if to_status not in TRANSITIONS.get(order.status, set()):
        raise OrderError(f"Cannot move order from {order.status} to {to_status}.", 400)

    old = order.status
    order.status = to_status

    if to_status == S.CONFIRMED:
        order.confirmed_at = timezone.now()
        order.confirmed_by = by
        order.needs_confirmation_call = False

    order.save()

    if to_status in (S.CANCELLED, S.FAILED):
        for item in order.items.exclude(product__isnull=True):
            if item.product.stock is not None:
                Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)
        order.items.update(status=OrderItem.Status.CANCELLED)

    if to_status == S.DELIVERED and order.customer:
        customer = order.customer
        delivered = Order.objects.filter(customer=customer, status=S.DELIVERED).count()
        if delivered >= 3:
            customer.trust_level = Customer.TrustLevel.REPEAT
            customer.save(update_fields=["trust_level"])
        elif customer.trust_level == Customer.TrustLevel.NEW:
            customer.trust_level = Customer.TrustLevel.VERIFIED
            customer.save(update_fields=["trust_level"])

    OrderStatusHistory.objects.create(
        order=order,
        from_status=old,
        to_status=to_status,
        changed_by=by if (by is not None and by.is_authenticated) else None,
        note=note[:255],
    )

    return order