import html
import logging
import secrets
from hmac import compare_digest
from api.services import generate_unique_product_slug
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from decimal import InvalidOperation
from api.models import (
    Adress,
    ProductVariant,
    Products,
    Order,
    OrderStatus,
)
from api.services import add_to_cart, remove_cart_item, update_cart_item

from . import keyboards
from .formatters import cart_text, money, order_text, product_text, tracking_text
from .services import (
    TelegramAPIError,
    clear_state,
    conversation,
    create_address,
    create_product_from_state,
    create_seller_for_account,
    customer_addresses,
    get_or_create_account,
    parse_decimal,
    parse_positive_int,
    safe_error,
    seller_orders,
    seller_products,
    seller_settlements,
    set_state,
    store_telegram_photo,
    telegram_sender,
    checkout_for_account,
)

logger = logging.getLogger(__name__)


def _user_from_update(update):
    if update.get('message'):
        return update['message'].get('from'), update['message'].get('chat', {}).get('id'), update['message'].get('text', '')
    callback = update.get('callback_query', {})
    message = callback.get('message', {})
    return callback.get('from'), message.get('chat', {}).get('id'), ''


def _send(chat_id, text, markup=None):
    try:
        return telegram_sender().send_message(chat_id, text, markup)
    except TelegramAPIError:
        logger.exception('Unable to send Telegram message')
        return None


def _send_product(chat_id, product, text, markup=None):
    image = getattr(product, 'image', None)
    image_url = getattr(image, 'url', None) if image else None
    if image_url:
        try:
            return telegram_sender().send_photo(chat_id, image_url, text, markup)
        except TelegramAPIError:
            logger.exception('Unable to send Telegram product photo')
    return _send(chat_id, text, markup)


def _main(account, chat_id, text='Welcome to Beminet 👋'):
    _send(chat_id, text, keyboards.main_menu(account))


def _callback(chat_id, callback_id, text=''):
    try:
        telegram_sender().answer_callback(callback_id, text)
    except TelegramAPIError:
        logger.exception('Unable to answer Telegram callback')


SHOP_PAGE_SIZE = 8


def _available_products():
    return (
        Products.objects.filter(
            status=Products.Status.APPROVED,
            is_sold_out=False,
            variants__is_active=True,
        )
        .prefetch_related('variants')
        .distinct()
        .order_by('-created_at', '-id')
    )


def _show_shop(chat_id, page=0):
    products = list(_available_products()[page * SHOP_PAGE_SIZE:(page + 1) * SHOP_PAGE_SIZE + 1])
    has_next = len(products) > SHOP_PAGE_SIZE
    products = products[:SHOP_PAGE_SIZE]
    if not products and page == 0:
        _send(chat_id, 'No products are available right now.')
        return
    for product in products:
        variants = list(product.variants.filter(is_active=True))
        price = min((variant.price for variant in variants), default=product.price)
        _send_product(
            chat_id,
            product,
            f'<b>{html.escape(product.name)}</b>\n{money(price)}',
            {'inline_keyboard': [[{'text': 'View product', 'callback_data': f'product:{product.id}'}]]},
        )
    rows = []
    if page:
        rows.append([{'text': 'Previous', 'callback_data': f'shop_page:{page - 1}'}])
    if has_next:
        rows.append([{'text': 'Next', 'callback_data': f'shop_page:{page + 1}'}])
    if rows:
        _send(chat_id, 'Browse products:', {'inline_keyboard': rows})


def _show_category(chat_id, category):
    products = _available_products().filter(category=category)
    rows = [[{'text': item.name, 'callback_data': f'product:{item.id}'}] for item in products]
    rows.append([{'text': '↩️ Back', 'callback_data': 'shop'}])
    _send(chat_id, f'🏷 <b>{html.escape(category.title())}</b>', {'inline_keyboard': rows})


def _show_product(chat_id, product_id):
    product = _available_products().filter(pk=product_id).first()
    if not product:
        _send(chat_id, 'Sorry, this product is currently unavailable.')
        return
    _send_product(chat_id, product, product_text(product), keyboards.product(product))
    variants = list(product.variants.filter(is_active=True).order_by('id'))
    if len(variants) > 1:
        _send(chat_id, 'Choose a variant:', keyboards.variants(variants, product.id))
    elif variants:
        _send(chat_id, 'Variant: ' + html.escape(variants[0].name), {'inline_keyboard': [[{'text': '🛒 Add to Cart', 'callback_data': f'variant:{product.id}:{variants[0].id}'}]]})


def _show_cart(account, chat_id):
    cart = account.user.cart if hasattr(account.user, 'cart') else None
    items = cart.items.select_related('product', 'variant').all() if cart else []
    _send(chat_id, cart_text(items), keyboards.cart_actions())


def _show_orders(account, chat_id):
    orders = account.user.order_set.prefetch_related('items', 'payment', 'delivery').order_by('-created_at')[:10]
    rows = []
    for order in orders:
        rows.append([{'text': f'#{order.order_number or order.pk} · {money(order.total)}', 'callback_data': f'order:{order.pk}'}])
    rows.append([{'text': '🏠 Main Menu', 'callback_data': 'home'}])
    _send(chat_id, '📦 <b>My Orders</b>', {'inline_keyboard': rows})


def _show_order(account, chat_id, order_id):
    order = account.user.order_set.prefetch_related('items', 'payment', 'delivery').filter(pk=order_id).first()
    if not order:
        _send(chat_id, 'That order was not found.')
        return
    _send(chat_id, order_text(order), {'inline_keyboard': [[{'text': '📦 Track Order', 'callback_data': f'track:{order.pk}'}], [{'text': '🏠 Main Menu', 'callback_data': 'home'}]]})


def _show_seller(account, chat_id):
    profile = getattr(account.user, 'seller_profile', None)
    if not profile:
        set_state(account, 'seller_name')
        _send(chat_id, 'Welcome to Beminet Seller 👋\n\nSell products on the Beminet marketplace without creating a shop.\n\nWhat is your name?')
        return
    if profile.status != 'active':
        _send(chat_id, f'Your seller application is currently <b>{profile.status}</b>. We will notify you after review.', keyboards.main_menu(account))
        return
    _send(chat_id, '🧑‍💼 <b>Seller Dashboard</b>', {'inline_keyboard': [
        [{'text': '➕ Add Product', 'callback_data': 'seller_add'}],
        [{'text': '📦 My Products', 'callback_data': 'seller_products'}, {'text': '🛒 My Orders', 'callback_data': 'seller_orders'}],
        [{'text': '💰 Settlements', 'callback_data': 'seller_settlements'}],
        [{'text': '🏠 Main Menu', 'callback_data': 'home'}],
    ]})


def _show_seller_products(account, chat_id):
    products = list(seller_products(account)[:20])

    if not products:
        _send(
            chat_id,
            '📦 <b>My Products</b>\n\n'
            'You have not added any products yet.',
            {
                'inline_keyboard': [
                    [{'text': '➕ Add Product', 'callback_data': 'seller_add'}],
                    [{'text': '↩️ Seller Dashboard', 'callback_data': 'seller'}],
                ]
            },
        )
        return

    for product in products:
        variant = product.variants.first()

        stock = (
            variant.inventory.available_quantity
            if variant and hasattr(variant, 'inventory')
            else 0
        )

        status_labels = {
            Products.Status.DRAFT: '📝 Draft',
            Products.Status.PENDING_REVIEW: '⏳ Pending Review',
            Products.Status.APPROVED: '✅ Approved',
            Products.Status.REJECTED: '❌ Rejected',
        }

        status = status_labels.get(
            product.status,
            product.status.replace('_', ' ').title(),
        )

        text = (
            f'<b>{html.escape(product.name)}</b>\n'
            f'{status} · Stock: {stock}\n'
            f'{money(product.price)}'
        )

        markup = {
            'inline_keyboard': [
                [
                    {
                        'text': '👁 View / Manage',
                        'callback_data': f'seller_product:{product.id}',
                    }
                ]
            ]
        }

        _send_product(
            chat_id,
            product,
            text,
            markup,
        )

    _send(
        chat_id,
        '📦 <b>My Products</b>',
        {
            'inline_keyboard': [
                [{'text': '➕ Add Product', 'callback_data': 'seller_add'}],
                [{'text': '↩️ Seller Dashboard', 'callback_data': 'seller'}],
            ]
        },
    )

def _show_seller_orders(account, chat_id):
    rows = []
    for order in seller_orders(account)[:20]:
        rows.append([{'text': f'#{order.order_number or order.pk} · {order.status}', 'callback_data': f'seller_order:{order.pk}'}])
    rows.append([{'text': '↩️ Seller Dashboard', 'callback_data': 'seller'}])
    _send(chat_id, '🛒 <b>My Orders</b>', {'inline_keyboard': rows})


def _show_seller_order(account, chat_id, order_id):
    order = seller_orders(account).filter(pk=order_id).first()
    if not order:
        _send(chat_id, 'That order was not found.')
        return
    relevant = [item for item in order.items.all() if item.seller_id == account.user.seller_profile.id]
    lines = [f'📦 <b>Order {order.order_number or order.pk}</b>', '']
    for item in relevant:
        lines.append(f'{item.product_name} × {item.quantity} · {money(item.line_total or item.price * item.quantity)}')
    lines.append(f'\nOrder status: {order.status}')
    _send(chat_id, '\n'.join(lines), {'inline_keyboard': [[{'text': '↩️ Seller Dashboard', 'callback_data': 'seller'}]]})


def _show_settlements(account, chat_id):
    settlements = seller_settlements(account)[:20]
    if not settlements:
        text = '💰 <b>Settlements</b>\n\nNo settlements yet.'
    else:
        lines = ['💰 <b>Settlements</b>', '']
        for item in settlements:
            lines.append(f'Order {item.order.order_number or item.order_id}: {money(item.amount)} · {item.status}')
        text = '\n'.join(lines)
    _send(chat_id, text, {'inline_keyboard': [[{'text': '↩️ Seller Dashboard', 'callback_data': 'seller'}]]})


def _address_prompt(account, chat_id):
    addresses = list(customer_addresses(account.user).filter(city='Hossana')[:10])
    rows = [[{'text': f'{item.city or item.address[:30]} · {item.phone_num}', 'callback_data': f'address:{item.id}'}] for item in addresses]
    rows.append([{'text': '➕ New Address', 'callback_data': 'new_address'}])
    rows.append([{'text': '❌ Cancel', 'callback_data': 'home'}])
    _send(chat_id, '📍 Choose a delivery address:', {'inline_keyboard': rows})


def _checkout_summary(account, chat_id, address_id):
    cart = account.user.cart
    items = cart.items.select_related('product', 'variant').all()
    subtotal = sum((item.unit_price or item.variant.price) * item.quantity for item in items)
    set_state(account, 'checkout_confirm', address_id=address_id, idempotency_key=f'tg-{account.telegram_user_id}-{secrets.token_hex(8)}')
    _send(chat_id, f'🧾 <b>Order Summary</b>\n\nSubtotal: {money(subtotal)}\nDelivery: {money(0)}\nTotal: {money(subtotal)}\n\n💵 Cash on Delivery', {'inline_keyboard': [[{'text': '✅ Confirm Order', 'callback_data': 'confirm_checkout'}], [{'text': '❌ Cancel', 'callback_data': 'home'}]]})


def _handle_text(account, chat_id, text):
    state = conversation(account)
    if text in ('/cancel', 'cancel', '❌ Cancel'):
        clear_state(account)
        _main(account, chat_id, 'Cancelled.')
        return
    if text.startswith('/'):
        command = text.split()[0].lower()
        if command == '/start':
            clear_state(account)
            _main(account, chat_id)
        elif command == '/shop':
            _show_shop(chat_id)
        elif command == '/cart':
            _show_cart(account, chat_id)
        elif command == '/orders':
            _show_orders(account, chat_id)
        elif command == '/seller':
            _show_seller(account, chat_id)
        elif command == '/help':
            _send(chat_id, 'Use /shop, /cart, /orders, /seller, /cancel, or the buttons below.', keyboards.main_menu(account))
        else:
            _send(chat_id, 'I did not recognize that command.', keyboards.main_menu(account))
        return
    data = dict(state.data)
    if state.state == 'seller_name':
        data['name'] = text
        set_state(account, 'seller_phone', **data)
        _send(chat_id, 'Please send your phone number.')
    elif state.state == 'seller_edit_name':
        product_id = state.data.get('product_id')

        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            clear_state(account)
            _send(chat_id, '❌ Product not found.')
            return

        new_name = text.strip()

        if not new_name:
            _send(chat_id, '❌ Product name cannot be empty.\n\nEnter the new product name:')
            return

        old_name = product.name

        product.name = new_name
        product.slug = generate_unique_product_slug(
            product.shop,
            new_name,
            exclude_product_id=product.id,
        )
        product.save(update_fields=['name', 'slug', 'updated_at'])

        clear_state(account)

        _send(
            chat_id,
            f'✅ <b>Product name updated!</b>\n\n'
            f'Old name: {html.escape(old_name)}\n'
            f'New name: <b>{html.escape(new_name)}</b>',
            {
                'inline_keyboard': [
                    [
                        {
                            'text': '✏️ Edit Again',
                            'callback_data': f'seller_product_edit:{product.id}',
                        }
                    ],
                    [
                        {
                            'text': '📦 My Products',
                            'callback_data': 'seller_products',
                        }
                    ],
                    [
                        {
                            'text': '↩️ Seller Dashboard',
                            'callback_data': 'seller',
                        }
                    ],
                ]
            },
        )
    elif state.state == 'seller_edit_description':
        product_id = state.data.get('product_id')

        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            clear_state(account)
            _send(chat_id, '❌ Product not found.')
            return

        new_description = text.strip()

        if not new_description:
            _send(
                chat_id,
                '❌ Description cannot be empty.\n\n'
                'Enter the new product description:'
            )
            return

        product.description = new_description
        product.save(update_fields=['description', 'updated_at'])

        clear_state(account)

        _send(
            chat_id,
            '✅ <b>Product description updated!</b>',
            {
                'inline_keyboard': [
                    [
                        {
                            'text': '✏️ Edit Again',
                            'callback_data': f'seller_product_edit:{product.id}',
                        }
                    ],
                    [
                        {
                            'text': '📦 My Products',
                            'callback_data': 'seller_products',
                        }
                    ],
                    [
                        {
                            'text': '↩️ Seller Dashboard',
                            'callback_data': 'seller',
                        }
                    ],
                ]
            },
        )
    elif state.state == 'seller_edit_price':
        product_id = state.data.get('product_id')

        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            clear_state(account)
            _send(chat_id, '❌ Product not found.')
            return

        try:
            new_price = parse_decimal(text.strip())

            if new_price <= 0:
                raise ValueError

        except (ValueError, TypeError, InvalidOperation):
            _send(
                chat_id,
                '❌ Invalid price.\n\n'
                'Enter a positive price in ETB, for example:\n'
                '<b>1500</b> or <b>1499.50</b>',
            )
            return

        product.price = new_price
        product.save(update_fields=['price', 'updated_at'])

        clear_state(account)

        _send(
            chat_id,
            f'✅ <b>Product price updated!</b>\n\n'
            f'New price: <b>{new_price} ETB</b>',
            {
                'inline_keyboard': [
                    [
                        {
                            'text': '✏️ Edit Again',
                            'callback_data': f'seller_product_edit:{product.id}',
                        }
                    ],
                    [
                        {
                            'text': '📦 My Products',
                            'callback_data': 'seller_products',
                        }
                    ],
                    [
                        {
                            'text': '↩️ Seller Dashboard',
                            'callback_data': 'seller',
                        }
                    ],
                ]
            },
        )
    elif state.state == 'seller_edit_stock':
        product_id = state.data.get('product_id')

        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            clear_state(account)
            _send(chat_id, '❌ Product not found.')
            return

        variant = product.variants.first()

        if not variant or not hasattr(variant, 'inventory'):
            clear_state(account)
            _send(chat_id, '❌ Product inventory was not found.')
            return

        try:
            new_stock = int(text.strip())

            if new_stock < 0:
                raise ValueError

        except (ValueError, TypeError):
            _send(
                chat_id,
                '❌ Invalid stock quantity.\n\n'
                'Enter a whole number such as <b>10</b>, <b>25</b>, or <b>0</b>:',
            )
            return

        variant.inventory.quantity_available = new_stock
        variant.inventory.save(update_fields=['quantity_available', 'updated_at'])

        clear_state(account)

        _send(
            chat_id,
            f'✅ <b>Product stock updated!</b>\n\n'
            f'New stock: <b>{new_stock}</b>',
            {
                'inline_keyboard': [
                    [
                        {
                            'text': '✏️ Edit Again',
                            'callback_data': f'seller_product_edit:{product.id}',
                        }
                    ],
                    [
                        {
                            'text': '📦 My Products',
                            'callback_data': 'seller_products',
                        }
                    ],
                    [
                        {
                            'text': '↩️ Seller Dashboard',
                            'callback_data': 'seller',
                        }
                    ],
                ]
            },
        )
    
    elif state.state == 'seller_phone':
        data['phone'] = text
        set_state(account, 'seller_display_name', **data)
        _send(chat_id, 'What display or business name should customers see?')
    elif state.state == 'seller_display_name':
        profile = create_seller_for_account(account, data['name'], data['phone'], text)
        clear_state(account)
        _send(chat_id, f'✅ Seller application submitted. Status: <b>{profile.status}</b>', keyboards.main_menu(account))
    elif state.state == 'address_area':
        data['area'] = text
        set_state(account, 'address_phone', **data)
        _send(chat_id, 'What phone number should we use for delivery?')
    elif state.state == 'address_phone':
        data['phone_number'] = text
        address = create_address(account.user, data)
        clear_state(account)
        _checkout_summary(account, chat_id, address.id)
    elif state.state.startswith('address_'):
        fields = ['full_name', 'phone_number', 'region', 'city', 'area', 'address_line', 'delivery_note']
        index = int(state.state.split('_')[1])
        data[fields[index]] = text
        if index + 1 < len(fields):
            set_state(account, f'address_{index + 1}', **data)
            _send(chat_id, f'Enter {fields[index + 1].replace("_", " ")}:')
        else:
            address = create_address(account.user, data)
            clear_state(account)
            _checkout_summary(account, chat_id, address.id)
    elif state.state == 'product_name':
        data['name'] = text
        set_state(account, 'product_description', **data)
        _send(chat_id, 'Enter the product description.')
    elif state.state == 'product_description':
        data['description'] = text
        set_state(account, 'product_photo', **data)
        _send(
            chat_id,
            'Send one product photo. Telegram currently stores it as the product primary image.'
        )
    elif state.state == 'product_price':
        data['price'] = text
        set_state(account, 'product_stock', **data)
        _send(chat_id, 'Enter available stock quantity.')
    elif state.state == 'product_stock':
        data['stock'] = text
        set_state(account, 'product_confirm', **data)
        _send(chat_id, 'Submit this product for review?', {'inline_keyboard': [[{'text': '✅ Submit Product', 'callback_data': 'seller_product_submit'}], [{'text': '📝 Save Draft', 'callback_data': 'seller_product_draft'}, {'text': '❌ Cancel', 'callback_data': 'home'}]]})
    elif state.state.startswith('cart_quantity:'):
        item_id = int(state.state.split(':')[1])
        try:
            update_cart_item(account.user, item_id, parse_positive_int(text))
            clear_state(account)
            _show_cart(account, chat_id)
        except Exception as exc:
            _send(chat_id, safe_error(exc))
    else:
        _send(chat_id, 'Please use the menu buttons.', keyboards.main_menu(account))


def _handle_photo(account, chat_id, photos):
    state = conversation(account)
    if state.state != 'product_photo':
        _send(chat_id, 'Please start a product submission before sending a product photo.')
        return
    if not photos:
        _send(chat_id, 'No product photo was received.')
        return
    try:
        largest = max(photos, key=lambda item: item.get('file_size', 0))
        public_id = store_telegram_photo(
            largest['file_id'],
            filename=f'telegram-product-{account.telegram_user_id}.jpg',
        )
        data = dict(state.data)
        data['image_public_id'] = public_id
        set_state(account, 'product_category', **data)
        _send(
            chat_id,
            '✅ Photo saved.\n\n📂 <b>Choose a product category:</b>',
            keyboards.product_categories(),
        )
    except Exception as exc:
        _send(chat_id, safe_error(exc
                                  ))


def _handle_callback(account, chat_id, callback_id, data):
    # Telegram requires every callback query to be answered.
    # Answer it exactly once here.
    _callback(chat_id, callback_id)
    if data == 'home':
        clear_state(account)
        _main(account, chat_id)
    elif data == 'shop':
        clear_state(account)
        _show_shop(chat_id)
    elif data.startswith('product_category:'):
        category = data.split(':', 1)[1]
        if conversation(account).state == 'seller_edit_category':
            product_id = conversation(account).data.get('product_id')

            product = seller_products(account).filter(pk=product_id).first()

            if not product:
                clear_state(account)
                _send(chat_id, '❌ Product not found.')
                return

            allowed_categories = {
                'shoes': 'Shoes',
                'clothes': 'Clothes',
                'bags': 'Bags',
                'beauty': 'Beauty',
                'electronics': 'Electronics',
                'home': 'Home & Living',
                'accessories': 'Accessories',
                'other': 'Other Category',
            }

            if category not in allowed_categories:
                _send(chat_id, '❌ Invalid product category.')
                return

            product.category = category
            product.save(update_fields=['category', 'updated_at'])

            clear_state(account)

            _send(
                chat_id,
                f'✅ <b>Product category updated!</b>\n\n'
                f'New category: <b>{html.escape(allowed_categories[category])}</b>',
                {
                    'inline_keyboard': [
                        [
                            {
                                'text': '✏️ Edit Again',
                                'callback_data': f'seller_product_edit:{product.id}',
                            }
                        ],
                        [
                            {
                                'text': '📦 My Products',
                                'callback_data': 'seller_products',
                            }
                        ],
                        [
                            {
                                'text': '↩️ Seller Dashboard',
                                'callback_data': 'seller',
                            }
                        ],
                    ]
                },
            )
            return

        allowed_categories = {
            'shoes': 'Shoes',
            'clothes': 'Clothes',
            'bags': 'Bags',
            'beauty': 'Beauty',
            'electronics': 'Electronics',
            'home': 'Home & Living',
            'accessories': 'Accessories',
            'other': 'Other Category',
        }

        if category not in allowed_categories:
            _send(chat_id, 'Invalid product category.')
            return

        state = conversation(account)

        if state.state != 'product_category':
            _send(chat_id, 'Please start adding a product first.')
            return

        state_data = dict(state.data)
        state_data['category'] = category

        set_state(
            account,
            'product_price',
            **state_data,
        )

        

        _send(
            chat_id,
            f'✅ Category: <b>{html.escape(allowed_categories[category])}</b>\n\n'
            'Enter the price in ETB.',
        )
    elif data.startswith('shop_page:'):
        _show_shop(chat_id, int(data.split(':', 1)[1]))
    elif data.startswith('category:'):
        _show_category(chat_id, data.split(':', 1)[1])
    elif data.startswith('product:'):
        _show_product(chat_id, int(data.split(':')[1]))
    elif data.startswith('add:') or data.startswith('buy:'):
        buy_now = data.startswith('buy:')
        product = _available_products().filter(pk=int(data.split(':')[1])).first()
        if not product:
            _send(chat_id, 'Sorry, this product is currently unavailable.')
            return
        variants = list(product.variants.filter(is_active=True).order_by('id'))
        if len(variants) != 1:
            if buy_now:
                set_state(account, f'buy_variant:{product.id}')
            _send(chat_id, 'Choose a variant:', keyboards.variants(variants, product.id))
            return
        try:
            add_to_cart(account.user, variants[0].id, 1)
            if buy_now:
                _address_prompt(account, chat_id)
            else:
                _send(chat_id, 'Added to cart.', {'inline_keyboard': [[{'text': 'View Cart', 'callback_data': 'cart'}]]})
        except Exception as exc:
            _send(chat_id, safe_error(exc))
    elif data.startswith('variant:'):
        _, product_id, variant_id = data.split(':')
        try:
            add_to_cart(account.user, int(variant_id), 1)
            if conversation(account).state == f'buy_variant:{product_id}':
                clear_state(account)
                _address_prompt(account, chat_id)
                return
            _send(chat_id, '✅ Added to cart.', {'inline_keyboard': [[{'text': '🛒 View Cart', 'callback_data': 'cart'}, {'text': '🛍 Continue Shopping', 'callback_data': 'shop'}]]})
        except Exception as exc:
            _send(chat_id, safe_error(exc))
    elif data == 'cart':
        _show_cart(account, chat_id)
    elif data == 'checkout':
        if not hasattr(account.user, 'cart') or not account.user.cart.items.exists():
            _send(chat_id, 'Your cart is empty.')
        else:
            _address_prompt(account, chat_id)
    elif data.startswith('address:'):
        _checkout_summary(account, chat_id, int(data.split(':')[1]))
    elif data == 'new_address':
        set_state(account, 'address_area')
        _send(chat_id, 'What area in Hossana are you in?')
    elif data == 'confirm_checkout':
        state = conversation(account)
        try:
            order = checkout_for_account(account, state.data['address_id'], state.data['idempotency_key'])
            clear_state(account)
            _send(chat_id, f'✅ <b>Order placed!</b>\n\nOrder: {order.order_number}\nTotal: {money(order.total)} ETB\nPayment: Cash on Delivery', {'inline_keyboard': [[{'text': '📦 Track Order', 'callback_data': f'track:{order.pk}'}], [{'text': '🏠 Main Menu', 'callback_data': 'home'}]]})
        except Exception as exc:
            _send(chat_id, safe_error(exc))
    elif data == 'orders':
        _show_orders(account, chat_id)
    elif data.startswith('order:'):
        _show_order(account, chat_id, int(data.split(':')[1]))
    elif data.startswith('track:'):
        order = account.user.order_set.filter(pk=int(data.split(':')[1])).first()
        _send(chat_id, tracking_text(order) if order else 'That order was not found.')
    elif data == 'account':
        _send(chat_id, f'👤 <b>{html.escape(account.user.username)}</b>\nPhone: {html.escape(account.user.phone_number or "Not set")}', keyboards.main_menu(account))
    elif data == 'help':
        _send(chat_id, 'Use the buttons to browse, manage your cart, checkout with COD, or apply as a seller.', keyboards.main_menu(account))
    elif data == 'seller_register' or data == 'seller':
        _show_seller(account, chat_id)
    elif data == 'seller_add':
        if not getattr(account.user, 'seller_profile', None) or account.user.seller_profile.status != 'active':
            _send(chat_id, 'Your seller profile must be active before adding products.')
        else:
            set_state(account, 'product_name')
            _send(chat_id, 'Enter the product name.')
    elif data == 'seller_products':
        _show_seller_products(account, chat_id)
    elif data == 'seller_orders':
        _show_seller_orders(account, chat_id)
    elif data.startswith('seller_order:'):
        _show_seller_order(account, chat_id, int(data.split(':')[1]))
    elif data == 'seller_settlements':
        _show_settlements(account, chat_id)
    elif data in ('seller_product_submit', 'seller_product_draft'):
        state = conversation(account)
        try:
            product = create_product_from_state(
                account,
                state.data,
                status=(
                    Products.Status.APPROVED
                    if data == 'seller_product_submit'
                    else Products.Status.DRAFT
                ),
            )
            if data == 'seller_product_submit':
                message = 'Product submitted for review.'
            else:
                message = '📝 Product saved as draft.'
            clear_state(account)
            _send(chat_id, message, keyboards.main_menu(account))
        except Exception as exc:
            _send(chat_id, safe_error(exc))
    elif data.startswith('seller_product_edit:'):
        product_id = int(data.split(':', 1)[1])
        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            _send(chat_id, '❌ Product not found.')
            return

        _send(
            chat_id,
            f'✏️ <b>Edit {html.escape(product.name)}</b>\n\n'
            'What would you like to change?',
            {
                'inline_keyboard': [
                    [
                        {
                            'text': '📝 Name',
                            'callback_data': f'seller_edit_name:{product.id}',
                        },
                    ],
                    [
                        {
                            'text': '📄 Description',
                            'callback_data': f'seller_edit_description:{product.id}',
                        },
                    ],
                    [
                        {
                            'text': '💰 Price',
                            'callback_data': f'seller_edit_price:{product.id}',
                        },
                    ],
                    [
                        {
                            'text': '📦 Stock',
                            'callback_data': f'seller_edit_stock:{product.id}',
                        },
                    ],
                    [
                        {
                            'text': '📂 Category',
                            'callback_data': f'seller_edit_category:{product.id}',
                        },
                    ],
                    [
                        {
                            'text': '↩️ Back',
                            'callback_data': f'seller_product:{product.id}',
                        }
                    ],
                ]
            },
        )
    elif data.startswith('seller_product_delete:'):
            product_id = int(data.split(':', 1)[1])
            product = seller_products(account).filter(pk=product_id).first()
    
            if not product:
                _send(chat_id, '❌ Product not found.')
                return
    
            _send(
                chat_id,
                f'⚠️ <b>Delete Product?</b>\n\n'
                f'{html.escape(product.name)}\n\n'
                'This action cannot be undone.',
                {
                    'inline_keyboard': [
                        [
                            {
                                'text': '🗑 Yes, Delete',
                                'callback_data': f'seller_product_delete_confirm:{product.id}',
                            }
                        ],
                        [
                            {
                                'text': '❌ Cancel',
                                'callback_data': f'seller_product:{product.id}',
                            }
                        ],
                    ]
                },
        )
    elif data.startswith('seller_product_delete_confirm:'):
            product_id = int(data.split(':', 1)[1])
    
            product = seller_products(account).filter(pk=product_id).first()
    
            if not product:
                _send(chat_id, '❌ Product not found.')
                return
    
            product_name = product.name
            product.delete()
    
            _send(
                chat_id,
                f'🗑 <b>{html.escape(product_name)}</b> was deleted.',
                {
                    'inline_keyboard': [
                        [
                            {
                                'text': '📦 My Products',
                                'callback_data': 'seller_products',
                            }
                        ],
                        [
                            {
                                'text': '↩️ Seller Dashboard',
                                'callback_data': 'seller',
                            }
                        ],
                    ]
                },
            )
    elif data.startswith('seller_edit_name:'):
        product_id = int(data.split(':', 1)[1])

        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            _send(chat_id, '❌ Product not found.')
            return

        set_state(
            account,
            'seller_edit_name',
            product_id=product.id,
        )

        _send(
            chat_id,
            f'✏️ <b>Edit Product Name</b>\n\n'
            f'Current name: <b>{html.escape(product.name)}</b>\n\n'
            'Enter the new product name:',
        )
    elif data.startswith('seller_edit_description:'):
        product_id = int(data.split(':', 1)[1])
        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            _send(chat_id, '❌ Product not found.')
            return

        set_state(
            account,
            'seller_edit_description',
            product_id=product.id,
        )

        _send(
            chat_id,
            f'✏️ <b>Edit Product Description</b>\n\n'
            f'Current description:\n'
            f'{html.escape(product.description or "No description")}\n\n'
            'Enter the new product description:',
        )

    elif data.startswith('seller_edit_price:'):
        product_id = int(data.split(':', 1)[1])

        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            _send(chat_id, '❌ Product not found.')
            return

        set_state(
            account,
            'seller_edit_price',
            product_id=product.id,
        )

        _send(
            chat_id,
            f'💰 <b>Edit Product Price</b>\n\n'
            f'Current price: <b>{product.price} ETB</b>\n\n'
            'Enter the new price in ETB:',
        )
    elif data.startswith('seller_edit_stock:'):
        product_id = int(data.split(':', 1)[1])

        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            _send(chat_id, '❌ Product not found.')
            return

        variant = product.variants.first()

        if not variant or not hasattr(variant, 'inventory'):
            _send(chat_id, '❌ Product inventory was not found.')
            return

        set_state(
            account,
            'seller_edit_stock',
            product_id=product.id,
        )

        _send(
            chat_id,
            f'📦 <b>Edit Product Stock</b>\n\n'
            f'Current stock: <b>{variant.inventory.quantity_available}</b>\n\n'
            'Enter the new stock quantity:',
        )
    elif data.startswith('seller_edit_category:'):
        product_id = int(data.split(':', 1)[1])

        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            _send(chat_id, '❌ Product not found.')
            return

        set_state(
            account,
            'seller_edit_category',
            product_id=product.id,
        )

        _send(
            chat_id,
            f'📂 <b>Edit Product Category</b>\n\n'
            f'Current category: <b>{html.escape(product.category)}</b>\n\n'
            'Choose the new category:',
            keyboards.product_categories(),
        )
    elif data.startswith('seller_product:'):
        product_id = int(data.split(':', 1)[1])
        product = seller_products(account).filter(pk=product_id).first()

        if not product:
            _send(chat_id, '❌ Product not found.')
            return

        variant = product.variants.first()

        stock = (
            variant.inventory.quantity_available
            if variant and hasattr(variant, 'inventory')
            else 0
        )

        status_labels = {
            Products.Status.DRAFT: '📝 Draft',
            Products.Status.PENDING_REVIEW: '⏳ Pending Review',
            Products.Status.APPROVED: '✅ Approved',
            Products.Status.REJECTED: '❌ Rejected',
        }

        status = status_labels.get(
            product.status,
            product.status.replace('_', ' ').title(),
        )

        text = (
            f'📦 <b>{html.escape(product.name)}</b>\n\n'
            f'<b>Status:</b> {status}\n'
            f'<b>Category:</b> {html.escape(product.category or "Other")}\n'
            f'<b>Price:</b> {money(product.price)}\n'
            f'<b>Stock:</b> {stock}\n\n'
            f'<b>Description:</b>\n'
            f'{html.escape(product.description or "No description")}'
        )

        markup = {
            'inline_keyboard': [
                [
                    {
                        'text': '✏️ Edit',
                        'callback_data': f'seller_product_edit:{product.id}',
                    },
                    {
                        'text': '🗑 Delete',
                        'callback_data': f'seller_product_delete:{product.id}',
                    },
                ],
                [
                    {
                        'text': '↩️ My Products',
                        'callback_data': 'seller_products',
                    }
                ],
            ]
        }

        _send_product(
            chat_id,
            product,
            text,
            markup,
        )
    elif data == 'cart_update' or data == 'cart_remove':
        cart = account.user.cart if hasattr(account.user, 'cart') else None
        items = list(cart.items.select_related('product', 'variant').all()) if cart else []
        if not items:
            _send(chat_id, 'Your cart is empty.')
            return
        action = 'cartqty' if data == 'cart_update' else 'cartremove'
        rows = [[{'text': f'{item.product.name} × {item.quantity}', 'callback_data': f'{action}:{item.id}'}] for item in items]
        rows.append([{'text': '↩️ Back to Cart', 'callback_data': 'cart'}])
        _send(chat_id, 'Choose an item:', {'inline_keyboard': rows})
    elif data.startswith('cartqty:'):
        set_state(account, f'cart_quantity:{int(data.split(":")[1])}')
        _send(chat_id, 'Enter the new positive quantity.')
   
    elif data.startswith('cartremove:'):
        try:
            remove_cart_item(account.user, int(data.split(':')[1]))
            _show_cart(account, chat_id)
        except Exception as exc:
            _send(chat_id, safe_error(exc))
    elif data.startswith('admin_order:'):
        order_id = int(data.split(':', 1)[1])
        _show_admin_order(account, chat_id, order_id)
    elif data.startswith('admin_order_confirm:'):
        if not account.user.is_staff:
            _send(chat_id, '❌ You are not authorized to confirm orders.')
            return

        order_id = int(data.split(':', 1)[1])

        order = Order.objects.filter(pk=order_id).first()

        if not order:
            _send(chat_id, '❌ That order was not found.')
            return

        if order.status != OrderStatus.PENDING:
            _send(
                chat_id,
                f'⚠️ This order is already <b>{order.status}</b>.',
            )
            return

        order.status = OrderStatus.CONFIRMED
        order.save(update_fields=['status', 'updated_at'])

        _send(
            chat_id,
            (
                f'✅ <b>Order Confirmed</b>\n\n'
                f'Order: #{order.order_number}\n'
                f'Status: <b>{order.status}</b>'
            ),
            {
                'inline_keyboard': [
                    [
                        {
                            'text': '📋 View Order',
                            'callback_data': f'admin_order:{order.id}',
                        }
                    ],
                    [
                        {
                            'text': '🏠 Main Menu',
                            'callback_data': 'home',
                        }
                    ],
                ]
            },
        )


def process_update(update):
    telegram_user, chat_id, text = _user_from_update(update)
    if not telegram_user or chat_id is None:
        return
    account = get_or_create_account(telegram_user)
    update_id = update.get('update_id')
    state = conversation(account)
    last_update_id = state.last_update_id
    if update_id is not None and last_update_id is not None and update_id <= last_update_id:
        return
    state.last_update_id = update_id
    state.save(update_fields=['last_update_id', 'updated_at'])
    callback = update.get('callback_query')
    if callback:
        _handle_callback(account, chat_id, callback['id'], callback.get('data', ''))
    elif update.get('message', {}).get('photo'):
        _handle_photo(account, chat_id, update['message']['photo'])
    else:
        _handle_text(account, chat_id, text)


@csrf_exempt
@require_POST
def webhook(request):
    configured_secret = settings.TELEGRAM_WEBHOOK_SECRET
    provided_secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not configured_secret or not provided_secret or not compare_digest(configured_secret, provided_secret):
        return JsonResponse({'detail': 'Forbidden'}, status=403)
    try:
        process_update(request.body and request.body.decode('utf-8') and __import__('json').loads(request.body) or {})
    except Exception:
        logger.exception('Telegram update processing failed')
    return JsonResponse({'ok': True})

def _show_admin_order(account, chat_id, order_id):
    if not account.user.is_staff:
        _send(chat_id, '❌ You are not authorized to view this order.')
        return

    order = (
        Order.objects
        .prefetch_related('items')
        .select_related('shipping_address')
        .filter(pk=order_id)
        .first()
    )

    if not order:
        _send(chat_id, '❌ That order was not found.')
        return

    lines = [
        '🛒 <b>ORDER DETAILS</b>',
        '',
        f'<b>Order:</b> #{order.order_number or order.pk}',
        f'<b>Status:</b> {order.status}',
        f'<b>Total:</b> {money(order.total)} ETB',
        f'<b>Customer:</b> {html.escape(order.customer_phone or "Not provided")}',
        '',
        '<b>📦 Items:</b>',
    ]

    for item in order.items.all():
        name = item.product_name or item.product.name

        if item.variant_name:
            name = f'{name} ({item.variant_name})'

        lines.append(
            f'• {html.escape(name)} × {item.quantity} '
            f'— {money(item.line_total or item.price * item.quantity)}'
        )

    if order.shipping_address:
        lines.extend([
            '',
            '<b>📍 Delivery:</b>',
            html.escape(
                getattr(order.shipping_address, 'address', None)
                or 'Not provided'
            ),
        ])

    lines.extend([
        '',
        f'<b>💵 Payment:</b> {order.get_payment_method_display()}',
    ])

    if order.notes:
        lines.extend([
            '',
            '<b>📝 Notes:</b>',
            html.escape(order.notes),
        ])

    _send(
        chat_id,
        '\n'.join(lines),
        keyboards.admin_order_actions(order.id),
    )