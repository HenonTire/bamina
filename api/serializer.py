from rest_framework.serializers import ModelSerializer
from .models import *
from manager.serializer import ShopeSerializer
from rest_framework import serializers

class ProductSerializer(ModelSerializer):
    shope = ShopeSerializer(read_only=True)
    class Meta:
        model = Products
        fields = ['id', 'name', 'description', 'price','discount_price','image', 'category', 'size', 'shope']

   
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
    class Meta:
        model = WhishList
        fields = ['id', 'user', 'products']
        read_only_fields = ['id', 'user', 'products' ]
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)
    
class CartItemSerializer(ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['id', 'user', 'product']
        read_only_fields = ['id', 'user', 'product']
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)
class OrderItemSerializer(ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'price']

class OrderSerializer(ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'total', 'status', 'shipping_address', 'payment_method', 'items']
        read_only_fields = ['id', 'user', 'total', 'status', 'items']

