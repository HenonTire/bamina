def button(text, callback_data):
    return {'text': text, 'callback_data': callback_data}


def main_menu(account):
    rows = [
        [button('🛍 Shop', 'shop'), button('🛒 Cart', 'cart')],
        [button('📦 My Orders', 'orders'), button('👤 My Account', 'account')],
        [button('☎️ Help', 'help')],
    ]
    if hasattr(account.user, 'seller_profile'):
        rows.insert(1, [button('🧑‍💼 Seller Dashboard', 'seller')])
    else:
        rows.insert(1, [button('🧑‍💼 Become a Seller', 'seller_register')])
    return {'inline_keyboard': rows}


def product_categories():
    return {
        'inline_keyboard': [
            [
                {'text': '👟 Shoes', 'callback_data': 'product_category:shoes'},
                {'text': '👕 Clothes', 'callback_data': 'product_category:clothes'},
            ],
            [
                {'text': '👜 Bags', 'callback_data': 'product_category:bags'},
                {'text': '💄 Beauty', 'callback_data': 'product_category:beauty'},
            ],
            [
                {'text': '📱 Electronics', 'callback_data': 'product_category:electronics'},
                {'text': '🏠 Home & Living', 'callback_data': 'product_category:home'},
            ],
            [
                {'text': '🎒 Accessories', 'callback_data': 'product_category:accessories'},
                {'text': '📦 Other Category', 'callback_data': 'product_category:other'},
            ],
            [
                {'text': '❌ Cancel', 'callback_data': 'home'},
            ],
        ]
    }

def product(product):
    return {'inline_keyboard': [
        [button('🛒 Add to Cart', f'add:{product.id}')],
        [button('⚡ Buy Now', f'buy:{product.id}')],
        [button('↩️ Back', 'shop')],
    ]}


def variants(variant_list, product_id):
    return {'inline_keyboard': [[button(item.name, f'variant:{product_id}:{item.id}')] for item in variant_list] + [[button('↩️ Back', f'product:{product_id}')]]}


def cart_actions():
    return {'inline_keyboard': [
        [button('➕ Continue Shopping', 'shop')],
        [button('✏️ Update Quantity', 'cart_update'), button('🗑 Remove', 'cart_remove')],
        [button('✅ Checkout', 'checkout')],
        [button('🏠 Main Menu', 'home')],
    ]}

def admin_order_actions(order_id):
    return {
        'inline_keyboard': [
            [
                button(
                    '📋 View Order',
                    f'admin_order:{order_id}',
                ),
            ],
        ]
    }
def admin_confirmed_order_actions(order_id):
    return {
        'inline_keyboard': [
            [
                button(
                    '⚙️ Start Processing',
                    f'admin_order_processing:{order_id}',
                ),
            ],
            [
                button(
                    '📋 View Order',
                    f'admin_order:{order_id}',
                ),
            ],
        ]
    }


def admin_processing_order_actions(order_id):
    return {
        'inline_keyboard': [
            [
                button(
                    '📦 Ready for Delivery',
                    f'admin_order_ready:{order_id}',
                ),
            ],
            [
                button(
                    '📋 View Order',
                    f'admin_order:{order_id}',
                ),
            ],
        ]
    }


def admin_ready_order_actions(order_id):
    return {
        'inline_keyboard': [
            [
                button(
                    '🚚 Out for Delivery',
                    f'admin_order_out:{order_id}',
                ),
            ],
            [
                button(
                    '📋 View Order',
                    f'admin_order:{order_id}',
                ),
            ],
        ]
    }

def seller_order_actions(order_id):
    return {
        'inline_keyboard': [
            [
                button(
                    '✅ Accept Order',
                    f'seller_order_accept:{order_id}',
                ),
                button(
                    '❌ Reject Order',
                    f'seller_order_reject:{order_id}',
                ),
            ],
            [
                button(
                    '📋 View Order',
                    f'seller_order:{order_id}',
                ),
            ],
        ]
    }