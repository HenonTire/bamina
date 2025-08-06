from django.db import models
from manager.models import Shop
from django.contrib.auth import get_user_model
User = get_user_model()
class Size(models.TextChoices):
    SMALL = 'small', 'Small'
    MEDIUM = 'medium', 'Medium'
    LAGRE = 'large', 'Large'
    XL = 'xl', 'Xl'


class Category(models.TextChoices):
    POPULAR_PICKS = 'popular_picks', 'Popular Picks'
    BAG =  "bag", "Bag"
    CLOTHE = "clothe", "Clothe"
    SHOES = "shoes", "Shoes"
    
class Products(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(max_length=500)
    image = models.ImageField(upload_to='producy-image/')
    price = models.DecimalField(decimal_places=2, max_digits=5)
    discount_price = models.DecimalField(decimal_places=2, max_digits=5, blank=True, null=True)
    size = models.CharField(max_length=30, choices=Size.choices, default=Size.MEDIUM)
    category = models.CharField(max_length=50, choices=Category, default=Category.POPULAR_PICKS, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

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

class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash on Delivery'
    PAY_HERE = 'pay_here', 'Card Payment'
class Order(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='shop', blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total = models.DecimalField(decimal_places=2, max_digits=10)
    status = models.CharField(max_length=100, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    shipping_address = models.TextField(max_length=500)
    payment_method = models.CharField(max_length=50, choices=PaymentMethod.choices, default=PaymentMethod.CASH)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(decimal_places=2, max_digits=10)  # Price at time of order

    def get_total_price(self):
        return self.price * self.quantity

class Adress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.address}"