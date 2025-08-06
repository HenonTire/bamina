from django.shortcuts import render
from .models import Shop
from .serializer import ShopeSerializer
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView, ListAPIView
from rest_framework.response import Response
from api.models import Products
from api.serializer import ProductSerializer
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db import models
from api.models import Order
from api.serializer import OrderSerializer
from django.utils import timezone
from api.models import OrderStatus

class RegisterShopeView(CreateAPIView):
    queryset = Shop.objects.all()
    serializer_class = ShopeSerializer

class CreateProduct(CreateAPIView):
    serializer_class = ProductSerializer
    queryset = Products.objects.all()
    permission_classes = [IsAdminUser]


    def perform_create(self, serializer):
        shop_id = self.kwargs.get('shop_id')
        try:
            shop = Shop.objects.get(shope_id=shop_id)  # or id=shop_id if using default PK
            serializer.save(shop=shop)
        except Shop.DoesNotExist:
            raise serializers.ValidationError("Shop does not exist.")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['shop_id'] = self.kwargs.get('shop_id')
        return context

class TotalRevenueView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, shop_id):
        try:
            shop = Shop.objects.get(shope_id=shop_id)
            total_revenue = shop.products_set.aggregate(total=models.Sum('price'))['total']
            return Response({'total_revenue': total_revenue})
        except Shop.DoesNotExist:
            raise ValidationError("Shop does not exist.")

class TotalOrderView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, shop_id):
        try:
            shop = Shop.objects.get(shope_id=shop_id)
            total_orders = Order.objects.filter(shop=shop).count()
            return Response({'total_orders': total_orders})
        except Shop.DoesNotExist:
            raise ValidationError("Shop does not exist.")
class ListShopProducts(ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        return Products.objects.filter(shop__shope_id=shop_id)
    
class ProductDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        return Products.objects.filter(shop__shope_id=shop_id)
    
    def perform_update(self, serializer):
        shop_id = self.kwargs.get('shop_id')
        try:
            shop = Shop.objects.get(shope_id=shop_id)
            serializer.save(shop=shop)
        except Shop.DoesNotExist:
            raise serializers.ValidationError("Shop does not exist.")
        
class ListOrderView(ListCreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        return Order.objects.filter(shop__shope_id=shop_id)

class OrderDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        return Order.objects.filter(shop__shope_id=shop_id)
    
    def perform_update(self, serializer):
        shop_id = self.kwargs.get('shop_id')
        try:
            shop = Shop.objects.get(shope_id=shop_id)
            serializer.save(shop=shop)
        except Shop.DoesNotExist:
            raise serializers.ValidationError("Shop does not exist.")
        
class ListShopUsers(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, shop_id):
        try:
            shop = Shop.objects.get(shope_id=shop_id)
            users = shop.user_set.all()
            user_data = []
            for user in users:
                profile_value = None
                if hasattr(user, 'profile') and user.profile:
                    try:
                        profile_value = user.profile.url
                    except ValueError:
                        profile_value = None
                user_data.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'profile': profile_value
                })
            return Response({'users': user_data})
        except Shop.DoesNotExist:
            raise ValidationError("Shop does not exist.")

class ShopProductNumByCategory(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, shop_id):
        try:
            shop = Shop.objects.get(shope_id=shop_id)
            category_counts = shop.products_set.values('category').annotate(count=models.Count('id'))
            return Response({'category_counts': category_counts})
        except Shop.DoesNotExist:
            raise ValidationError("Shop does not exist.")
        

