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


def categories(categories):
    return {'inline_keyboard': [[button(str(value).title(), f'category:{value}')] for value in categories] + [[button('↩️ Back', 'home')]]}


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
