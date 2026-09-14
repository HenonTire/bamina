from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from manager.models import Shop
from user.models import SellerProfile, User, TelegramAccount

from .models import Adress, Delivery, Inventory, OrderStatus, Payment, ProductVariant, Products, Settlement
from .services import add_to_cart, checkout, transition_delivery, transition_order


class CoreCommerceServiceTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name='Beminet', shope_id='beminet', is_marketplace=True)
        self.user = User.objects.create_user(email='customer@example.com', password='pass1234', username='customer')
        self.seller_user = User.objects.create_user(email='seller@example.com', password='pass1234', username='seller')
        self.seller = SellerProfile.objects.create(
            user=self.seller_user,
            display_name='Seller One',
            status=SellerProfile.Status.ACTIVE,
        )
        self.product = Products.objects.create(
            shop=self.shop,
            seller=self.seller,
            name='Shoes',
            description='A pair of shoes',
            price=Decimal('100.00'),
            status=Products.Status.APPROVED,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name='Black / 40',
            sku='SHOE-BLACK-40',
            price=Decimal('100.00'),
        )
        Inventory.objects.create(variant=self.variant, quantity_available=5)
        self.address = Adress.objects.create(
            user=self.user,
            address='Main Street',
            phone_num='',
        )

    def test_adding_same_variant_updates_one_cart_row(self):
        add_to_cart(self.user, self.variant.id, 1)
        item = add_to_cart(self.user, self.variant.id, 2)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(self.user.cart.items.count(), 1)

    def test_checkout_creates_one_cod_order_and_reserves_inventory(self):
        add_to_cart(self.user, self.variant.id, 2)
        order = checkout(self.user, self.address, 'checkout-1')

        self.assertEqual(order.subtotal, Decimal('200.00'))
        self.assertEqual(order.total, Decimal('200.00'))
        self.assertEqual(order.payment.status, Payment.Status.PENDING)
        self.assertEqual(order.delivery.status, Delivery.Status.PENDING)
        self.assertEqual(order.items.get().line_total, Decimal('200.00'))
        self.assertEqual(order.items.get().seller_id, self.seller.id)
        self.assertEqual(Inventory.objects.get(variant=self.variant).quantity_reserved, 2)

    def test_checkout_supports_beminet_owned_product_without_a_seller(self):
        product = Products.objects.create(
            shop=self.shop,
            name='Beminet Bag',
            description='Marketplace-owned bag',
            price=Decimal('75.00'),
            status=Products.Status.APPROVED,
            seller=None,
        )
        variant = ProductVariant.objects.create(product=product, sku='BEM-BAG-1', price=Decimal('75.00'))
        Inventory.objects.create(variant=variant, quantity_available=2)

        add_to_cart(self.user, variant.id, 1)
        order = checkout(self.user, self.address, 'beminet-owned-checkout')

        self.assertIsNone(order.items.get().seller)
        self.assertEqual(Inventory.objects.get(variant=variant).quantity_reserved, 1)

    def test_checkout_is_idempotent(self):
        add_to_cart(self.user, self.variant.id, 1)
        first = checkout(self.user, self.address, 'checkout-retry')
        second = checkout(self.user, self.address, 'checkout-retry')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.user.order_set.count(), 1)

    def test_insufficient_stock_rolls_back_order(self):
        add_to_cart(self.user, self.variant.id, 6)
        with self.assertRaises(ValidationError):
            checkout(self.user, self.address, 'checkout-fails')
        self.assertEqual(self.user.order_set.count(), 0)
        self.assertEqual(self.variant.inventory.quantity_reserved, 0)

    def test_delivery_completion_collects_cod_and_creates_seller_settlement(self):
        add_to_cart(self.user, self.variant.id, 1)
        order = checkout(self.user, self.address, 'checkout-delivery')
        for status in [OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.READY_FOR_DELIVERY, OrderStatus.OUT_FOR_DELIVERY]:
            order = transition_order(order, status)
        transition_delivery(order.delivery, Delivery.Status.ASSIGNED)
        transition_delivery(order.delivery, Delivery.Status.PICKED_UP)
        transition_delivery(order.delivery, Delivery.Status.OUT_FOR_DELIVERY)
        transition_delivery(order.delivery, Delivery.Status.DELIVERED)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.DELIVERED)
        self.assertEqual(order.payment.status, Payment.Status.COLLECTED)
        self.assertEqual(Settlement.objects.filter(order=order, seller=self.seller).count(), 1)
        inventory = Inventory.objects.get(variant=self.variant)
        self.assertEqual(inventory.quantity_available, 4)
        self.assertEqual(inventory.quantity_reserved, 0)

    def test_telegram_user_id_is_unique(self):
        TelegramAccount.objects.create(telegram_user_id=123, user=self.user)
        with self.assertRaises(Exception):
            TelegramAccount.objects.create(telegram_user_id=123, user=self.seller_user)
