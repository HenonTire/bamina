import logging
import secrets
from decimal import Decimal, InvalidOperation

import httpx
from cloudinary import uploader
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from api.models import Adress, CartItem, Notification, Order, ProductVariant, Products, Settlement
from api.services import marketplace_shop
from api.services import (
    add_to_cart,
    checkout,
    create_seller_product,
    generate_unique_sku,
    get_cart,
    remove_cart_item,
    update_cart_item,
)
from user.models import SellerProfile, TelegramAccount, User

from .models import ConversationState

logger = logging.getLogger(__name__)

def notify_admins_telegram(title, body):
    admins = User.objects.filter(
        is_staff=True,
        is_active=True,
    ).select_related('telegram_account')

    client = TelegramClient()

    for admin in admins:
        account = getattr(admin, 'telegram_account', None)

        if not account or not account.telegram_user_id:
            continue

        try:
            client.send_message(
                account.telegram_user_id,
                f'<b>{title}</b>\n\n{body}',
            )
        except Exception:
            logger.exception(
                'Failed to notify admin %s via Telegram',
                admin.id,
            )
def notify_admins(title, body):
    """
    Keep the existing database notification for staff users.

    Telegram notifications for orders are handled separately by
    notify_order_parties().
    """
    shop = marketplace_shop()
    if not shop:
        return

    for admin in User.objects.filter(is_staff=True, is_active=True):
        Notification.objects.create(
            user=admin,
            shop=shop,
            title=title,
            body=body,
        )
def notify_order_parties(order):
    """
    Notify admins and sellers about a newly created order.

    - Admins receive the complete order.
    - Each seller receives only their own products.
    - A seller receives only ONE notification even if they have
      multiple products in the same order.
    """

    items = list(
        order.items.select_related(
            'product',
            'seller',
        )
    )

    # Group order items by seller.
    # seller_id=None means the product belongs to Beminet.
    sellers = {}

    for item in items:
        if item.seller_id is not None:
            sellers.setdefault(item.seller_id, []).append(item)

    client = TelegramClient()

    # =========================================================
    # ADMIN NOTIFICATION
    # =========================================================

    admins = User.objects.filter(
        is_staff=True,
        is_active=True,
    ).select_related('telegram_account')

    item_lines = []

    for item in items:
        name = item.product_name or item.product.name

        if item.variant_name:
            name = f'{name} ({item.variant_name})'

        item_lines.append(
            f'• {name} × {item.quantity} — {item.line_total or item.get_total_price()} ETB'
        )

    address = order.shipping_address

    delivery_address = (
        getattr(address, 'address', None)
        or 'Not provided'
    )

    payment_method = (
        str(order.get_payment_method_display())
        if hasattr(order, 'get_payment_method_display')
        else str(order.payment_method)
    )

    admin_lines = [
        '<b>🛒 NEW ORDER</b>',
        '',
        f'<b>Order:</b> #{order.order_number}',
        f'<b>Total:</b> {order.total} ETB',
        f'<b>Customer:</b> {order.customer_phone or "Not provided"}',
        '',
        '<b>📦 Items:</b>',
        *item_lines,
        '',
        '<b>📍 Delivery:</b>',
        delivery_address,
        '',
        f'<b>💵 Payment:</b> {payment_method}',
    ]

    if order.notes:
        admin_lines.extend([
            '',
            '<b>📝 Customer Notes:</b>',
            order.notes,
        ])

    admin_lines.extend([
        '',
        '<b>⚡ ACTION REQUIRED</b>',
        'Please confirm and process this order.',
    ])

    admin_message = '\n'.join(admin_lines)

    for admin in admins:
        account = getattr(admin, 'telegram_account', None)

        if not account or not account.telegram_user_id:
            continue

        try:
            client.send_message(
                account.telegram_user_id,
                admin_message,
            )
        except Exception:
            logger.exception(
                'Failed to notify admin %s about order %s',
                admin.id,
                order.order_number,
            )

    # =========================================================
    # SELLER NOTIFICATIONS
    # =========================================================

    for seller_id, seller_items in sellers.items():

        seller = seller_items[0].seller

        account = getattr(
            seller.user,
            'telegram_account',
            None,
        )

        if not account or not account.telegram_user_id:
            continue

        seller_item_lines = []
        seller_total = Decimal('0')

        for item in seller_items:
            name = item.product_name or item.product.name

            if item.variant_name:
                name = f'{name} ({item.variant_name})'

            line_total = item.line_total or item.get_total_price()
            seller_total += line_total

            seller_item_lines.append(
                f'• {name} × {item.quantity} — {line_total} ETB'
            )

        seller_lines = [
            '<b>🛒 NEW ORDER</b>',
            '',
            f'<b>Order:</b> #{order.order_number}',
            '',
            '<b>📦 Your Products:</b>',
            *seller_item_lines,
            '',
            f'<b>💰 Your Order Value:</b> {seller_total} ETB',
            '',
            '<b>👤 Customer:</b>',
            order.customer_phone or 'Not provided',
            '',
            '<b>📍 Delivery:</b>',
            delivery_address,
            '',
            f'<b>💵 Payment:</b> {payment_method}',
        ]

        if order.notes:
            seller_lines.extend([
                '',
                '<b>📝 Customer Notes:</b>',
                order.notes,
            ])

        seller_lines.extend([
            '',
            '<b>⚡ ACTION REQUIRED</b>',
            'Please prepare your products for pickup.',
        ])

        seller_message = '\n'.join(seller_lines)

        try:
            client.send_message(
                account.telegram_user_id,
                seller_message,
            )
        except Exception:
            logger.exception(
                'Failed to notify seller %s about order %s',
                seller.id,
                order.order_number,
            )
class TelegramAPIError(Exception):
    pass


class TelegramClient:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f'https://api.telegram.org/bot{self.token}'

    def call(self, method, payload=None):
        if not self.token:
            raise TelegramAPIError('Telegram bot token is not configured.')
        try:
            response = httpx.post(f'{self.base_url}/{method}', json=payload or {}, timeout=15)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise TelegramAPIError('Telegram API request failed.') from exc
        if not data.get('ok'):
            raise TelegramAPIError(data.get('description', 'Telegram API error.'))
        return data.get('result')

    def send_message(self, chat_id, text, reply_markup=None):
        payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if reply_markup:
            payload['reply_markup'] = reply_markup
        return self.call('sendMessage', payload)

    def send_photo(self, chat_id, photo, caption='', reply_markup=None):
        payload = {'chat_id': chat_id, 'photo': photo, 'caption': caption, 'parse_mode': 'HTML'}
        if reply_markup:
            payload['reply_markup'] = reply_markup
        return self.call('sendPhoto', payload)

    def answer_callback(self, callback_id, text=''):
        return self.call('answerCallbackQuery', {'callback_query_id': callback_id, 'text': text})

    def get_file(self, file_id):
        return self.call('getFile', {'file_id': file_id})

    def download_file(self, file_path):
        if not self.token:
            raise TelegramAPIError('Telegram bot token is not configured.')
        try:
            response = httpx.get(
                f'https://api.telegram.org/file/bot{self.token}/{file_path}',
                timeout=30,
            )
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise TelegramAPIError('Telegram file download failed.') from exc


def telegram_sender():
    return TelegramClient()


def store_telegram_photo(file_id, filename='telegram-product.jpg'):
    try:
        telegram = telegram_sender()
        file_info = telegram.get_file(file_id)
        file_path = file_info.get('file_path') if file_info else None
        if not file_path:
            raise TelegramAPIError('Telegram did not return a file path.')
        content = telegram.download_file(file_path)
        if not content:
            raise TelegramAPIError('Telegram returned an empty file.')
        result = uploader.upload(
            content,
            folder='products/',
            resource_type='image',
            use_filename=True,
            filename_override=filename,
        )
        public_id = result.get('public_id') if result else None
        if not public_id:
            raise TelegramAPIError('Image storage did not return an image ID.')
        return public_id
    except TelegramAPIError:
        raise
    except Exception as exc:
        logger.exception('Telegram product photo storage failed')
        raise TelegramAPIError('Product photo storage failed.') from exc


def get_or_create_account(telegram_user):
    telegram_id = int(telegram_user['id'])
    username = telegram_user.get('username', '') or ''
    with transaction.atomic():
        account = TelegramAccount.objects.select_for_update().filter(telegram_user_id=telegram_id).first()
        if account is None:
            user = User(
                email=f'telegram-{telegram_id}@telegram.local',
                username=(username or f'telegram_{telegram_id}')[:100],
                first_name=telegram_user.get('first_name', '')[:100],
                last_name=telegram_user.get('last_name', '')[:100],
                role=User.Role.CUSTOMER,
                is_verified=False,
            )
            user.set_unusable_password()
            user.save()
            account = TelegramAccount.objects.create(
                telegram_user_id=telegram_id,
                telegram_username=username,
                user=user,
                is_verified=True,
            )
        else:
            account.telegram_username = username
            if account.user_id is None:
                user = User.objects.create(
                    email=f'telegram-{telegram_id}@telegram.local',
                    username=(username or f'telegram_{telegram_id}')[:100],
                    role=User.Role.CUSTOMER,
                )
                user.set_unusable_password()
                user.save()
                account.user = user
            account.save(update_fields=['telegram_username', 'user', 'updated_at'])
    return account


def conversation(account):
    state, _ = ConversationState.objects.get_or_create(account=account)
    return state


def set_state(account, state, **data):
    conversation_state = conversation(account)
    conversation_state.state = state
    conversation_state.data = data
    conversation_state.save(update_fields=['state', 'data', 'updated_at'])
    return conversation_state


def clear_state(account):
    conversation(account).clear()


def parse_decimal(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValidationError('Enter a valid price.')
    if amount <= 0:
        raise ValidationError('Price must be positive.')
    return amount


def parse_positive_int(value):
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        raise ValidationError('Enter a valid quantity.')
    if quantity <= 0:
        raise ValidationError('Quantity must be positive.')
    return quantity


def customer_addresses(user):
    return Adress.objects.filter(user=user).order_by('-is_default', '-created_at')


def create_address(user, data):
    area = data['area'].strip()
    phone_number = data['phone_number'].strip()
    address, _ = Adress.objects.get_or_create(
        user=user,
        city='Hossana',
        area=area,
        phone_num=phone_number,
        defaults={'address': area, 'address_line': area},
    )
    return address


def create_seller_for_account(account, name, phone, display_name):
    user = account.user
    user.first_name = name[:100]
    user.phone_number = phone[:20]
    user.role = User.Role.SELLER
    user.save(update_fields=['first_name', 'phone_number', 'role', 'updated_at'])
    profile, _ = SellerProfile.objects.get_or_create(
        user=user,
        defaults={'display_name': display_name[:255], 'status': SellerProfile.Status.ACTIVE},
    )
    if profile.display_name != display_name:
        profile.display_name = display_name[:255]
        profile.save(update_fields=['display_name', 'updated_at'])
    notify_admins('New seller application', f'{profile.display_name} submitted a seller application.')
    return profile


def seller_products(account):
    return Products.objects.filter(seller__user=account.user).prefetch_related('variants__inventory').order_by('-created_at')


def seller_orders(account):
    return Order.objects.filter(items__seller__user=account.user).distinct().prefetch_related('items', 'payment', 'delivery').order_by('-created_at')


def seller_settlements(account):
    return Settlement.objects.filter(seller__user=account.user).select_related('order').order_by('-created_at')


def create_product_from_state(account, data, status=Products.Status.APPROVED):
    seller = getattr(account.user, 'seller_profile', None)
    if not seller or seller.status != SellerProfile.Status.ACTIVE:
        raise ValidationError('Your seller profile is not active yet.')
    product = create_seller_product(
        seller=seller,
        name=data['name'],
        description=data['description'],
        category=data['category'],
        variant_name='Default',
        sku=generate_unique_sku(),
        price=parse_decimal(data['price']),
        stock=parse_positive_int(data['stock']),
    )
    product.status = status
    update_fields = ['status', 'updated_at']
    if data.get('image_public_id'):
        product.image = data['image_public_id']
        update_fields.insert(0, 'image')
    product.save(update_fields=update_fields)
    notify_admins_telegram(
    '📦 New Seller Product',
    f'{product.name} was submitted by {seller.display_name}.',
)
    notify_admins('New seller product', f'{product.name} was submitted by {seller.display_name}.')
    return product


def checkout_for_account(account, address_id, idempotency_key, notes=''):
    address = Adress.objects.get(pk=address_id, user=account.user)
    return checkout(account.user, address, idempotency_key, notes=notes)


def safe_error(exc):
    logger.exception('Telegram bot operation failed', exc_info=exc)
    if isinstance(exc, ValidationError):
        detail = exc.detail
        if isinstance(detail, list):
            return str(detail[0])
        if isinstance(detail, dict):
            return str(next(iter(detail.values())))
        return str(detail)
    return 'Sorry, something went wrong. Please try again.'
