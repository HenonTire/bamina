from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from manager.models import Shop
from telegram_bot.services import notify_order_parties
from user.models import SellerProfile

from .models import (
    Cart,
    CartItem,
    Delivery,
    Inventory,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    ProductVariant,
    Products,
    Settlement,
)


def marketplace_shop():
    return Shop.objects.filter(is_active=True, is_marketplace=True).first() or Shop.objects.filter(is_active=True).order_by('id').first()


def generate_unique_sku():
    """Return a unique SKU for automatically-created product variants."""
    while True:
        sku = f'BEM-{uuid4().hex.upper()}'
        if not ProductVariant.objects.filter(sku=sku).exists():
            return sku


def get_or_create_variant(product, variant=None):
    if variant is not None:
        if variant.product_id != product.id or not variant.is_active:
            raise ValidationError('The selected variant is not available.')
        return variant

    existing = product.variants.filter(is_active=True).order_by('id').first()
    if existing:
        return existing

    sku = f'{slugify(product.name)[:80] or "product"}-{product.pk}'
    variant = ProductVariant.objects.create(
        product=product,
        name='Default',
        sku=sku,
        price=product.price,
    )
    Inventory.objects.create(variant=variant, quantity_available=0)
    return variant


def get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def add_to_cart(user, variant_id, quantity=1):
    if quantity <= 0:
        raise ValidationError('Quantity must be positive.')
    variant = ProductVariant.objects.select_related('product').get(pk=variant_id)
    if variant.product.status != Products.Status.APPROVED or not variant.is_active:
        raise ValidationError('This product is not available.')
    cart = get_cart(user)
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={
            'user': user,
            'product': variant.product,
            'quantity': quantity,
            'unit_price': variant.price,
        },
    )
    if not created:
        item.quantity += quantity
        item.unit_price = variant.price
        item.save(update_fields=['quantity', 'unit_price', 'updated_at'])
    return item


def update_cart_item(user, item_id, quantity):
    if quantity <= 0:
        raise ValidationError('Quantity must be positive.')
    item = CartItem.objects.get(pk=item_id, cart__user=user)
    item.quantity = quantity
    item.unit_price = item.variant.price
    item.save(update_fields=['quantity', 'unit_price', 'updated_at'])
    return item


def remove_cart_item(user, item_id):
    item = CartItem.objects.get(pk=item_id, cart__user=user)
    item.delete()


def create_cod_payment(order):
    return Payment.objects.create(
        order=order,
        method=PaymentMethod.COD,
        status=Payment.Status.PENDING,
        amount=order.total,
    )


def create_delivery(order):
    return Delivery.objects.create(
        order=order,
        status=Delivery.Status.PENDING,
        delivery_fee=order.delivery_fee,
    )


def _order_number():
    return f'BEM-{timezone.now():%Y%m%d}-{uuid4().hex[:8].upper()}'


def checkout(user, shipping_address, idempotency_key, delivery_fee=Decimal('0'), notes=''):
    if not idempotency_key:
        raise ValidationError('An idempotency key is required.')

    with transaction.atomic():
        existing = Order.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.user_id != user.id:
                raise ValidationError('This idempotency key belongs to another customer.')
            return existing

        cart = Cart.objects.select_for_update().get(user=user)
        items = list(
            CartItem.objects.select_for_update(of=('self',))
            .select_related('product', 'variant__product')
            .filter(cart=cart)
        )
        if not items:
            raise ValidationError('Your cart is empty.')
        if shipping_address.user_id != user.id:
            raise ValidationError('The address does not belong to this customer.')

        subtotal = Decimal('0')
        for item in items:
            variant = item.variant or get_or_create_variant(item.product)
            product = variant.product
            if product.status != Products.Status.APPROVED or not variant.is_active:
                raise ValidationError(f'{product.name} is not available.')
            inventory = Inventory.objects.select_for_update().get(variant=variant)
            if inventory.available_quantity < item.quantity:
                raise ValidationError(f'Insufficient stock for {product.name}.')
            subtotal += variant.price * item.quantity

        delivery_fee = Decimal(delivery_fee)
        total = subtotal + delivery_fee
        order = Order.objects.create(
            order_number=_order_number(),
            user=user,
            shop=marketplace_shop(),
            total=total,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            payment_method=PaymentMethod.COD,
            status=OrderStatus.PENDING,
            shipping_address=shipping_address,
            customer_phone=shipping_address.phone_num,
            notes=notes,
            idempotency_key=idempotency_key,
        )

        for item in items:
            variant = item.variant or get_or_create_variant(item.product)
            inventory = Inventory.objects.select_for_update().get(variant=variant)
            inventory.quantity_reserved += item.quantity
            inventory.save(update_fields=['quantity_reserved', 'updated_at'])
            line_total = variant.price * item.quantity
            OrderItem.objects.create(
                order=order,
                product=variant.product,
                variant=variant,
                seller=variant.product.seller,
                product_name=variant.product.name,
                variant_name=variant.name,
                sku=variant.sku,
                quantity=item.quantity,
                price=variant.price,
                line_total=line_total,
            )

        create_cod_payment(order)
        create_delivery(order)
        items_qs = CartItem.objects.filter(cart=cart)
        items_qs.delete()
    notify_order_parties(order)
    return order


ORDER_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.READY_FOR_DELIVERY, OrderStatus.CANCELLED},
    OrderStatus.READY_FOR_DELIVERY: {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED, OrderStatus.FAILED},
    OrderStatus.FAILED: {OrderStatus.RETURNED},
}


def transition_order(order, new_status):
    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if new_status not in ORDER_TRANSITIONS.get(locked.status, set()):
            raise ValidationError(f'Cannot transition order from {locked.status} to {new_status}.')
        locked.status = new_status
        locked.save(update_fields=['status', 'updated_at'])
        if new_status == OrderStatus.CANCELLED:
            for item in locked.items.select_related('variant__inventory'):
                if item.variant_id:
                    inventory = Inventory.objects.select_for_update().get(variant=item.variant)
                    if inventory.quantity_reserved >= item.quantity:
                        inventory.quantity_reserved -= item.quantity
                        inventory.save(update_fields=['quantity_reserved', 'updated_at'])
        return locked


def transition_delivery(delivery, new_status, failure_reason=''):
    allowed = {
        Delivery.Status.PENDING: {Delivery.Status.ASSIGNED},
        Delivery.Status.ASSIGNED: {Delivery.Status.PICKED_UP},
        Delivery.Status.PICKED_UP: {Delivery.Status.OUT_FOR_DELIVERY},
        Delivery.Status.OUT_FOR_DELIVERY: {Delivery.Status.DELIVERED, Delivery.Status.FAILED},
        Delivery.Status.FAILED: {Delivery.Status.RETURNED},
    }
    with transaction.atomic():
        locked = Delivery.objects.select_for_update().get(pk=delivery.pk)
        if new_status not in allowed.get(locked.status, set()):
            raise ValidationError(f'Cannot transition delivery from {locked.status} to {new_status}.')
        locked.status = new_status
        now = timezone.now()
        if new_status == Delivery.Status.PICKED_UP:
            locked.picked_up_at = now
        elif new_status == Delivery.Status.DELIVERED:
            locked.delivered_at = now
        elif new_status == Delivery.Status.FAILED:
            locked.failed_at = now
            locked.failure_reason = failure_reason
        locked.save()
        if new_status == Delivery.Status.DELIVERED:
            order = Order.objects.select_for_update().get(pk=locked.order_id)
            if order.status != OrderStatus.OUT_FOR_DELIVERY:
                raise ValidationError('Order must be out for delivery first.')
            for item in order.items.select_related('variant'):
                if item.variant_id:
                    Inventory.objects.select_for_update().get(variant=item.variant).confirm(item.quantity)
            order.status = OrderStatus.DELIVERED
            order.save(update_fields=['status', 'updated_at'])
            payment = Payment.objects.select_for_update().get(order=order)
            payment.status = Payment.Status.COLLECTED
            payment.collected_at = now
            payment.save(update_fields=['status', 'collected_at', 'updated_at'])
            create_settlements(order)
        return locked


def create_settlements(order):
    for item in order.items.select_related('seller'):
        if item.seller_id:
            Settlement.objects.get_or_create(
                order=order,
                seller=item.seller,
                defaults={
                    'amount': item.line_total or item.price * item.quantity,
                    'platform_fee': Decimal('0'),
                    'delivery_amount': Decimal('0'),
                    'status': Settlement.Status.READY,
                },
            )


PRODUCT_TRANSITIONS = {
    Products.Status.DRAFT: {Products.Status.PENDING_REVIEW},
    Products.Status.PENDING_REVIEW: {Products.Status.APPROVED, Products.Status.REJECTED},
    Products.Status.APPROVED: {Products.Status.SUSPENDED, Products.Status.ARCHIVED},
    Products.Status.SUSPENDED: {Products.Status.APPROVED, Products.Status.ARCHIVED},
    Products.Status.REJECTED: {Products.Status.DRAFT, Products.Status.ARCHIVED},
}


def transition_product(product, new_status):
    with transaction.atomic():
        locked = Products.objects.select_for_update().get(pk=product.pk)
        if new_status not in PRODUCT_TRANSITIONS.get(locked.status, set()):
            raise ValidationError(f'Cannot transition product from {locked.status} to {new_status}.')
        locked.status = new_status
        locked.save(update_fields=['status', 'updated_at'])
        return locked


def create_seller_product(seller, name, description, category, variant_name, sku, price, stock, slug=''):
    if seller.status != SellerProfile.Status.ACTIVE:
        raise ValidationError('Seller profile is not active.')
    shop = marketplace_shop()
    if not shop:
        raise ValidationError('The marketplace shop is not configured.')
    with transaction.atomic():
        product = Products.objects.create(
            shop=shop,
            seller=seller,
            name=name,
            slug=slug or None,
            description=description,
            price=price,
            category=category,
            status=Products.Status.DRAFT,
        )
        variant = ProductVariant.objects.create(
            product=product,
            name=variant_name or 'Default',
            sku=sku,
            price=price,
        )
        Inventory.objects.create(variant=variant, quantity_available=stock)
    return product


def collect_cod(payment):
    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.method != PaymentMethod.COD or locked.status != Payment.Status.PENDING:
            raise ValidationError('Only pending COD payments can be collected.')
        if locked.order.status != OrderStatus.DELIVERED:
            raise ValidationError('COD can only be collected for delivered orders.')
        locked.status = Payment.Status.COLLECTED
        locked.collected_at = timezone.now()
        locked.save(update_fields=['status', 'collected_at', 'updated_at'])
        return locked
