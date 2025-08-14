from django.shortcuts import render
from .models import Shop, ShopOwner
from .serializer import ShopeSerializer
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView, ListAPIView
from rest_framework.response import Response
from api.models import Products
from api.serializer import ProductSerializer
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db import models
from api.models import Order
from api.serializer import OrderSerializer
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .permission import IsOwnerOfShop
from user.helper import set_refresh_cookie
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterShopeView(CreateAPIView):
    permission_classes = []
    queryset = Shop.objects.all()
    serializer_class = ShopeSerializer


class CreateProduct(CreateAPIView):
    serializer_class = ProductSerializer
    queryset = Products.objects.all()
    permission_classes = [IsOwnerOfShop]

    def perform_create(self, serializer):
        shop_id = self.kwargs.get('shop_id')
        try:
            # or id=shop_id if using default PK
            shop = Shop.objects.get(shope_id=shop_id)
            serializer.save(shop=shop)
        except Shop.DoesNotExist:
            raise serializers.ValidationError("Shop does not exist.")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['shop_id'] = self.kwargs.get('shop_id')
        return context


class TotalRevenueView(APIView):
    permission_classes = [IsOwnerOfShop]

    def get(self, request, shop_id):
        try:
            shop = Shop.objects.get(shope_id=shop_id)
            total_revenue = shop.products_set.aggregate(
                total=models.Sum('price'))['total'] or 0

            if total_revenue is None:
                total_revenue = 0
            return Response({'total_revenue': total_revenue})
        except Shop.DoesNotExist:
            raise ValidationError("Shop does not exist.")


class TotalOrderView(APIView):
    permission_classes = [IsOwnerOfShop]

    def get(self, request, shop_id):
        try:
            shop = Shop.objects.get(shope_id=shop_id)
            total_orders = Order.objects.filter(shop=shop).count()
            return Response({'total_orders': total_orders})
        except Shop.DoesNotExist:
            raise ValidationError("Shop does not exist.")


class ListShopProducts(ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsOwnerOfShop]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        return Products.objects.filter(shop__shope_id=shop_id)


class ProductDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsOwnerOfShop]

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


class ListOrderView(ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsOwnerOfShop]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        return Order.objects.filter(shop__shope_id=shop_id)


class OrderDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsOwnerOfShop]

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
    permission_classes = [IsOwnerOfShop]

    def get(self, request, shop_id):
        try:
            shop = Shop.objects.get(shope_id=shop_id)
            users = User.objects.filter(shopowner__shop=shop)

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
    permission_classes = [IsOwnerOfShop]

    def get(self, request, shop_id):
        try:
            shop = Shop.objects.get(shope_id=shop_id)
            category_counts = shop.products_set.values(
                'category').annotate(count=models.Count('id'))
            return Response({'category_counts': category_counts})
        except Shop.DoesNotExist:
            raise ValidationError("Shop does not exist.")


class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        user = authenticate(request, username=email, password=password)

        if user is not None:
            # Check if this user is a shop owner
            shop_owner = ShopOwner.objects.filter(user=user).first()
            if shop_owner:
                refresh = RefreshToken.for_user(user)

                response_data = {
                    'access': str(refresh.access_token),
                    'username': user.username,
                    'shop_id': shop_owner.shop.shope_id
                }

                # Create response and attach refresh token as cookie
                response = Response(response_data, status=status.HTTP_200_OK)
                set_refresh_cookie(response, refresh)

                return response

        return Response(
            {'error': 'Invalid credentials or not admin'},
            status=status.HTTP_401_UNAUTHORIZED
        )
