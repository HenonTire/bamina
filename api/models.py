from django.db import models
from manager.models import Shop
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField
from django.db import transaction
from django.core.exceptions import ValidationError
from user.models import SellerProfile

from . import validators

User = get_user_model()


class Size(models.TextChoices):
    SMALL = 'small', 'Small'
    MEDIUM = 'medium', 'Medium'
    LARGE = 'large', 'Large'
    XL = 'xl', 'Xl'


class Category(models.TextChoices):
    POPULAR_PICKS = "popular_picks", "Popular Picks"
    # POPULAR_PICKS = 'popular_picks', 'Popular Picks'
    BAGS = "bags", "Bags"
    CLOTHES = "clothes", "Clothes"
    SHOES = "shoes", "Shoes"


class Products(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    seller = models.ForeignKey(SellerProfile, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='products')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True, null=True)
    description = models.TextField(max_length=500)
    image = CloudinaryField('product_image', blank=True,
                            null=True, folder="products/")
    price = models.DecimalField(decimal_places=2, max_digits=10)
    discount_price = models.DecimalField(
        decimal_places=2, max_digits=10, blank=True, null=True)
    size = models.CharField(
        max_length=30, choices=Size.choices, default=Size.MEDIUM)
    is_sold_out = models.BooleanField(default=False)
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING_REVIEW = 'pending_review', 'Pending review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        SUSPENDED = 'suspended', 'Suspended'
        ARCHIVED = 'archived', 'Archived'

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APPROVED)
    category = models.CharField(max_length=50, choices=Category,
                                default=Category.CLOTHES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['shop', 'slug'], name='unique_product_slug_per_shop'),
        ]


class ProdyctFeedback(models.Model):
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=0)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.product.name} - {self.rating}"


class ShopFeedBack(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=0)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.shop.name} - {self.rating}"


class WhishList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    products = models.ManyToManyField(Products, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Wishlist"


class CartItem(models.Model):
    cart = models.ForeignKey('Cart', on_delete=models.CASCADE, null=True, blank=True, related_name='items')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    variant = models.ForeignKey('ProductVariant', on_delete=models.PROTECT, null=True, blank=True,
                                related_name='legacy_cart_items')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_total_price(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    IN_PROCESS = 'in_process', 'In_process'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'
    CONFIRMED = 'confirmed', 'Confirmed'
    PROCESSING = 'processing', 'Processing'
    READY_FOR_DELIVERY = 'ready_for_delivery', 'Ready for delivery'
    OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for delivery'
    FAILED = 'failed', 'Failed'
    RETURNED = 'returned', 'Returned'


class PaymentMethod(models.TextChoices):
    COD = 'cod', 'Cash on delivery'

# class PaymentMethod(models.TextChoices):
#     CASH = 'cash', 'Cash on Delivery'
#     PAY_HERE = 'pay_here', 'Card Payment'


class Adress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.TextField(max_length=500)
    phone_num = models.CharField(max_length=13, blank=True, default='', validators=[
                                 validators.ethiopian_phone_validator])
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    full_name = models.CharField(max_length=255, blank=True, default='')
    region = models.CharField(max_length=100, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    area = models.CharField(max_length=100, blank=True, default='')
    address_line = models.TextField(blank=True, default='')
    delivery_note = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.address}"


class Order(models.Model):
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='shop', blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total = models.DecimalField(decimal_places=2, max_digits=10)
    created_at = models.DateTimeField(auto_now_add=True)
    # payment_method = models.CharField(max_length=50, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    shipping_address = models.ForeignKey(
        Adress, on_delete=models.SET_NULL, blank=True, null=True, related_name="orders")
    status = models.CharField(
        max_length=50,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING
    )
    order_number = models.CharField(max_length=32, unique=True, null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    subtotal = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    delivery_fee = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    customer_phone = models.CharField(max_length=20, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    variant = models.ForeignKey('ProductVariant', on_delete=models.PROTECT, null=True, blank=True)
    seller = models.ForeignKey(SellerProfile, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=100, blank=True, default='')
    variant_name = models.CharField(max_length=100, blank=True, default='')
    sku = models.CharField(max_length=100, blank=True, default='')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(
        decimal_places=2, max_digits=10)  # Price at time of order
    line_total = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_total_price(self):
        return self.price * self.quantity


class ProductVariant(models.Model):
    product = models.ForeignKey(Products, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=100, default='Default')
    sku = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(decimal_places=2, max_digits=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Inventory(models.Model):
    variant = models.OneToOneField(ProductVariant, on_delete=models.CASCADE, related_name='inventory')
    quantity_available = models.PositiveIntegerField(default=0)
    quantity_reserved = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def available_quantity(self):
        return self.quantity_available - self.quantity_reserved

    def reserve(self, quantity):
        if quantity <= 0:
            raise ValidationError('Quantity must be positive.')
        with transaction.atomic():
            locked = Inventory.objects.select_for_update().get(pk=self.pk)
            if locked.available_quantity < quantity:
                raise ValidationError('Insufficient stock.')
            locked.quantity_reserved += quantity
            locked.save(update_fields=['quantity_reserved', 'updated_at'])
        self.refresh_from_db()

    def release(self, quantity):
        if quantity <= 0:
            raise ValidationError('Quantity must be positive.')
        with transaction.atomic():
            locked = Inventory.objects.select_for_update().get(pk=self.pk)
            if locked.quantity_reserved < quantity:
                raise ValidationError('Cannot release more stock than reserved.')
            locked.quantity_reserved -= quantity
            locked.save(update_fields=['quantity_reserved', 'updated_at'])
        self.refresh_from_db()

    def confirm(self, quantity):
        if quantity <= 0:
            raise ValidationError('Quantity must be positive.')
        with transaction.atomic():
            locked = Inventory.objects.select_for_update().get(pk=self.pk)
            if locked.quantity_reserved < quantity or locked.quantity_available < quantity:
                raise ValidationError('Reserved stock is insufficient.')
            locked.quantity_available -= quantity
            locked.quantity_reserved -= quantity
            locked.save(update_fields=['quantity_available', 'quantity_reserved', 'updated_at'])
        self.refresh_from_db()

    def adjust(self, quantity):
        with transaction.atomic():
            locked = Inventory.objects.select_for_update().get(pk=self.pk)
            new_quantity = locked.quantity_available + quantity
            if new_quantity < locked.quantity_reserved:
                raise ValidationError('Stock cannot be below reserved quantity.')
            locked.quantity_available = new_quantity
            locked.save(update_fields=['quantity_available', 'updated_at'])
        self.refresh_from_db()


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COLLECTED = 'collected', 'Collected'
        FAILED = 'failed', 'Failed'

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(decimal_places=2, max_digits=10)
    collected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Delivery(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ASSIGNED = 'assigned', 'Assigned'
        PICKED_UP = 'picked_up', 'Picked up'
        OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for delivery'
        DELIVERED = 'delivered', 'Delivered'
        FAILED = 'failed', 'Failed'
        RETURNED = 'returned', 'Returned'

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    delivery_fee = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    courier_name = models.CharField(max_length=255, blank=True, default='')
    courier_phone = models.CharField(max_length=20, blank=True, default='')
    tracking_code = models.CharField(max_length=100, blank=True, default='')
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Settlement(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        READY = 'ready', 'Ready'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='settlements')
    seller = models.ForeignKey(SellerProfile, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='settlements')
    amount = models.DecimalField(decimal_places=2, max_digits=10)
    platform_fee = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    delivery_amount = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order', 'seller'], name='unique_settlement_order_seller'),
        ]


class FCMToken(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="fcm_tokens")
    token = models.CharField(max_length=255, unique=True)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Notification(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} -> {self.user.username}"
