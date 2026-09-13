from decimal import Decimal
from .models import Notification
from rest_framework.serializers import ModelSerializer
from .models import *
from manager.serializer import ShopeSerializer
from rest_framework import serializers


class ProductSerializer(ModelSerializer):
    shope = ShopeSerializer(read_only=True)
    image_url = serializers.SerializerMethodField(read_only=True)
    image = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = Products
        fields = ['id', 'name', 'description', 'price',
                  'discount_price', 'image', 'image_url', 'category', 'size', 'shope', 'is_sold_out']

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class ProductFeedbackSerializer(ModelSerializer):
    class Meta:
        model = ProdyctFeedback
        fields = ['id', 'product', 'user', 'rating', 'comment']
        read_only_fields = ['id', 'user', 'product']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ShopFeedBackSerializer(ModelSerializer):
    class Meta:
        model = ShopFeedBack
        fields = ['id', 'shop', 'user', 'rating', 'comment']
        read_only_fields = ['id', 'user', 'shop']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class WhishlistSerializer(ModelSerializer):
    products = ProductSerializer(many=True, read_only=True)

    class Meta:
        model = WhishList
        fields = ['id', 'user', 'products']
        read_only_fields = ['id', 'user', 'products']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class CartItemSerializer(ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'user', 'product']
        read_only_fields = ['id', 'user', 'product']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class OrderItemSerializer(ModelSerializer):
    product = ProductSerializer(read_only=True, many=False)

    class Meta:
        model = OrderItem
        fields = ['product']


class AdressSerializer(ModelSerializer):
    class Meta:
        model = Adress
        fields = ['id', 'user', 'address',
                  'created_at', 'phone_num', 'is_default']
        read_only_fields = ['id', 'user', 'created_at', 'is_default']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class OrderSerializer(ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_address = AdressSerializer(many=False, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'total', 'status',
                  'shipping_address',  'items']
        read_only_fields = ['id', 'user', 'total', 'status', 'items']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "body", "created_at"]


class VariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ['id', 'product', 'name', 'sku', 'price', 'is_active']
        read_only_fields = ['id', 'product']


class CoreProductSerializer(serializers.ModelSerializer):
    variants = VariantSerializer(many=True, read_only=True)
    seller = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Products
        fields = ['id', 'name', 'slug', 'description', 'category', 'status', 'seller', 'variants', 'created_at', 'updated_at']
        read_only_fields = ['id', 'seller', 'status', 'created_at', 'updated_at']


class CoreCartItemSerializer(serializers.ModelSerializer):
    variant = VariantSerializer(read_only=True)
    product = CoreProductSerializer(source='variant.product', read_only=True)
    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'variant', 'product', 'quantity', 'unit_price', 'available_quantity']
        read_only_fields = ['id', 'variant', 'product', 'unit_price', 'available_quantity']

    def get_available_quantity(self, obj):
        return obj.variant.inventory.available_quantity if hasattr(obj.variant, 'inventory') else 0


class CoreAddressSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='phone_num')
    address_line = serializers.CharField(source='address')

    class Meta:
        model = Adress
        fields = ['id', 'full_name', 'phone_number', 'region', 'city', 'area', 'address_line', 'delivery_note', 'is_default', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_default', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class CoreOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'variant', 'seller', 'product_name', 'variant_name', 'sku', 'unit_price', 'quantity', 'line_total']


class CoreOrderSerializer(serializers.ModelSerializer):
    items = CoreOrderItemSerializer(many=True, read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    delivery_status = serializers.CharField(source='delivery.status', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'status', 'payment_method', 'subtotal', 'delivery_fee', 'total', 'shipping_address', 'customer_phone', 'notes', 'payment_status', 'delivery_status', 'items', 'created_at', 'updated_at']
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    shipping_address_id = serializers.IntegerField()
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), default=0)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class AddCartItemSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class SellerProductSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2, write_only=True)
    sku = serializers.CharField(write_only=True)
    initial_stock = serializers.IntegerField(min_value=0, write_only=True, default=0)

    class Meta:
        model = Products
        fields = ['id', 'name', 'slug', 'description', 'category', 'price', 'sku', 'initial_stock', 'status']
        read_only_fields = ['id', 'status']
