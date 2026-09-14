import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from api.models import Adress, Inventory, ProductVariant, Products
from manager.models import Shop
from user.models import SellerProfile, TelegramAccount, User

from .services import create_product_from_state, get_or_create_account, set_state, store_telegram_photo
from .views import process_update


class TelegramBotTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name='Beminet', shope_id='beminet', is_marketplace=True)
        self.user_data = {'id': 9001, 'username': 'telegram_customer', 'first_name': 'Customer'}
        self.product = Products.objects.create(
            shop=self.shop,
            name='Sneakers',
            description='Everyday sneakers',
            category='shoes',
            price=Decimal('1500.00'),
            status=Products.Status.APPROVED,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name='Black / 42',
            sku='SNK-BLK-42',
            price=Decimal('1500.00'),
        )
        Inventory.objects.create(variant=self.variant, quantity_available=10)

    def test_new_and_returning_telegram_account_reuse_user(self):
        first = get_or_create_account(self.user_data)
        second = get_or_create_account(self.user_data)
        self.assertEqual(first.user_id, second.user_id)
        self.assertEqual(TelegramAccount.objects.filter(telegram_user_id=9001).count(), 1)
        self.assertEqual(User.objects.filter(email='telegram-9001@telegram.local').count(), 1)

    @override_settings(TELEGRAM_BOT_TOKEN='test-token', TELEGRAM_WEBHOOK_SECRET='secret')
    @patch('telegram_bot.services.TelegramClient.send_message')
    @patch('telegram_bot.services.TelegramClient.answer_callback')
    def test_start_browse_and_add_variant(self, answer_callback, send_message):
        process_update({'update_id': 1, 'message': {'from': self.user_data, 'chat': {'id': 55}, 'text': '/start'}})
        process_update({'update_id': 2, 'callback_query': {'id': 'cb', 'from': self.user_data, 'message': {'chat': {'id': 55}}, 'data': 'category:shoes'}})
        process_update({'update_id': 3, 'callback_query': {'id': 'cb2', 'from': self.user_data, 'message': {'chat': {'id': 55}}, 'data': f'variant:{self.product.id}:{self.variant.id}'}})
        account = TelegramAccount.objects.get(telegram_user_id=9001)
        self.assertEqual(account.user.cart.items.get().quantity, 1)
        self.assertGreaterEqual(send_message.call_count, 3)

    @override_settings(TELEGRAM_BOT_TOKEN='test-token')
    @patch('telegram_bot.services.TelegramClient.send_message')
    @patch('telegram_bot.services.TelegramClient.answer_callback')
    def test_checkout_uses_core_service_and_duplicate_update_is_ignored(self, answer_callback, send_message):
        process_update({'update_id': 10, 'message': {'from': self.user_data, 'chat': {'id': 55}, 'text': '/start'}})
        account = TelegramAccount.objects.get(telegram_user_id=9001)
        from api.services import add_to_cart
        add_to_cart(account.user, self.variant.id, 1)
        address = Adress.objects.create(user=account.user, address='Bole', phone_num='')
        set_state(account, 'checkout_confirm', address_id=address.id, idempotency_key='tg-test-order')
        update = {'update_id': 11, 'callback_query': {'id': 'cb', 'from': self.user_data, 'message': {'chat': {'id': 55}}, 'data': 'confirm_checkout'}}
        process_update(update)
        process_update(update)
        self.assertEqual(account.user.order_set.count(), 1)

    def test_webhook_rejects_wrong_secret(self):
        with override_settings(TELEGRAM_WEBHOOK_SECRET='expected'):
            response = self.client.post(
                reverse('telegram-webhook'),
                data=json.dumps({'update_id': 1}),
                content_type='application/json',
                HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='wrong',
            )
        self.assertEqual(response.status_code, 403)

    def test_webhook_rejects_when_secret_is_not_configured(self):
        with override_settings(TELEGRAM_WEBHOOK_SECRET=''):
            response = self.client.post(
                reverse('telegram-webhook'),
                data=json.dumps({'update_id': 1}),
                content_type='application/json',
                HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='anything',
            )
        self.assertEqual(response.status_code, 403)

    def test_seller_registration_creates_pending_profile_without_shop(self):
        account = get_or_create_account(self.user_data)
        from .services import create_seller_for_account
        profile = create_seller_for_account(account, 'Jane', '0911000000', 'Jane Shop')
        self.assertEqual(profile.status, SellerProfile.Status.ACTIVE)
        self.assertIsNone(account.user.shop_id)

    def test_seller_orders_are_filtered_to_owned_items(self):
        seller_user = User.objects.create_user(email='seller@example.com', username='seller', password='pass')
        seller = SellerProfile.objects.create(user=seller_user, display_name='Seller', status=SellerProfile.Status.ACTIVE)
        account = TelegramAccount.objects.create(telegram_user_id=9002, user=seller_user)
        from api.services import add_to_cart, checkout, transition_order
        customer = User.objects.create_user(email='customer@example.com', username='customer', password='pass')
        address = Adress.objects.create(user=customer, address='Bole', phone_num='')
        self.product.seller = seller
        self.product.save(update_fields=['seller'])
        add_to_cart(customer, self.variant.id, 1)
        order = checkout(customer, address, 'seller-order-test')
        self.assertEqual(len(list(order.items.filter(seller=seller))), 1)

    @patch('telegram_bot.services.uploader.upload')
    @patch('telegram_bot.services.telegram_sender')
    def test_telegram_photo_is_downloaded_and_stored_in_cloudinary(self, telegram_sender, cloudinary_upload):
        telegram = telegram_sender.return_value
        telegram.get_file.return_value = {'file_path': 'photos/file.jpg'}
        telegram.download_file.return_value = b'fake-image-bytes'
        cloudinary_upload.return_value = {'public_id': 'products/telegram-photo'}

        public_id = store_telegram_photo('telegram-file-id')

        self.assertEqual(public_id, 'products/telegram-photo')
        telegram.get_file.assert_called_once_with('telegram-file-id')
        telegram.download_file.assert_called_once_with('photos/file.jpg')
        cloudinary_upload.assert_called_once()
        self.assertEqual(cloudinary_upload.call_args.kwargs['folder'], 'products/')

    @patch('telegram_bot.services.notify_admins')
    def test_stored_photo_is_attached_when_seller_product_is_created(self, notify_admins):
        seller_user = User.objects.create_user(email='photo-seller@example.com', username='photo-seller', password='pass')
        seller = SellerProfile.objects.create(user=seller_user, display_name='Photo Seller', status=SellerProfile.Status.ACTIVE)
        account = TelegramAccount.objects.create(telegram_user_id=9003, user=seller_user)

        product = create_product_from_state(account, {
            'name': 'Photo Shoes',
            'description': 'Shoes with a stored photo',
            'category': 'shoes',
            'variant_name': 'Default',
            'sku': 'PHOTO-SHOES-1',
            'price': '1200.00',
            'stock': '4',
            'image_public_id': 'products/telegram-photo',
        })

        product.refresh_from_db()
        self.assertEqual(str(product.image), 'products/telegram-photo')
        self.assertEqual(product.seller_id, seller.id)
        self.assertEqual(product.status, Products.Status.APPROVED)

    @patch('telegram_bot.views._send')
    @patch('telegram_bot.views.store_telegram_photo', return_value='products/photo-from-update')
    def test_photo_update_stores_public_id_and_continues_submission(self, store_photo, send):
        seller_user = User.objects.create_user(email='flow-seller@example.com', username='flow-seller', password='pass')
        SellerProfile.objects.create(user=seller_user, display_name='Flow Seller', status=SellerProfile.Status.ACTIVE)
        account = TelegramAccount.objects.create(telegram_user_id=9004, user=seller_user)
        set_state(account, 'product_photo', name='Flow Shoes', description='Flow description')

        process_update({
            'update_id': 40,
            'message': {
                'from': {'id': 9004, 'username': 'flow-seller'},
                'chat': {'id': 400},
                'photo': [
                    {'file_id': 'small', 'width': 100, 'height': 100, 'file_size': 10},
                    {'file_id': 'large', 'width': 1000, 'height': 1000, 'file_size': 100},
                ],
            },
        })

        account.refresh_from_db()
        self.assertEqual(account.conversation_state.state, 'product_category')
        self.assertEqual(account.conversation_state.data['image_public_id'], 'products/photo-from-update')
        store_photo.assert_called_once_with('large', filename='telegram-product-9004.jpg')
