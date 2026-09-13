from decimal import Decimal


def money(value):
    return f'{Decimal(value):,.2f} ETB'


def product_text(product):
    variants = list(product.variants.filter(is_active=True).order_by('id'))
    prices = [item.price for item in variants]
    price = min(prices) if prices else product.price
    return f'🛍 <b>{product.name}</b>\n\n{product.description}\n\nPrice from {money(price)}'


def cart_text(items):
    if not items:
        return '🛒 <b>Your Cart</b>\n\nYour cart is empty.'
    lines = ['🛒 <b>Your Cart</b>', '']
    subtotal = Decimal('0')
    for item in items:
        variant_name = item.variant.name if item.variant_id else item.product.name
        price = item.unit_price or (item.variant.price if item.variant_id else item.product.price)
        line_total = price * item.quantity
        subtotal += line_total
        lines.append(f'{item.product.name} ({variant_name})\n{item.quantity} × {money(price)} = {money(line_total)}')
    lines.append(f'\nSubtotal: {money(subtotal)}')
    return '\n\n'.join(lines)


def order_text(order):
    payment = getattr(order, 'payment', None)
    delivery = getattr(order, 'delivery', None)
    lines = [
        f'📦 <b>Order {order.order_number or order.pk}</b>',
        '',
        f'Status: {order.status.replace("_", " ").title()}',
        f'Total: {money(order.total)}',
        f'Payment: {payment.status.title() if payment else "pending"}',
        f'Delivery: {delivery.status.replace("_", " ").title() if delivery else "pending"}',
        '',
    ]
    for item in order.items.all():
        lines.append(f'{item.product_name or item.product.name} × {item.quantity} = {money(item.line_total or item.price * item.quantity)}')
    return '\n'.join(lines)


def tracking_text(order):
    stages = ['confirmed', 'processing', 'ready_for_delivery', 'out_for_delivery', 'delivered']
    current = stages.index(order.status) if order.status in stages else -1
    labels = {
        'confirmed': 'Order confirmed',
        'processing': 'Processing',
        'ready_for_delivery': 'Ready for delivery',
        'out_for_delivery': 'Out for delivery',
        'delivered': 'Delivered',
    }
    lines = [f'📦 <b>Order {order.order_number or order.pk}</b>', '']
    for index, stage in enumerate(stages):
        marker = '✅' if index <= current else '⬜'
        if stage == 'out_for_delivery' and order.status == 'out_for_delivery':
            marker = '🚚'
        lines.append(f'{marker} {labels[stage]}')
    return '\n'.join(lines)
