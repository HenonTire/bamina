from django.shortcuts import get_object_or_404
from api.models import Products, Order
from manager.models import Shop, ShopOwner
from datetime import timedelta, datetime
from django.db.models import Sum, Count
from django.utils import timezone
from django.shortcuts import render
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
from api.serializer import OrderSerializer
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .permission import IsOwnerOfShop
from user.helper import set_refresh_cookie
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import UpdateAPIView, DestroyAPIView

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
            # users = User.objects.filter(shopowner__shop=shop)
            owners = User.objects.filter(shopowner__shop=shop)
            all_users = User.objects.filter(shop=shop)
            users = (all_users | owners).distinct()

            user_data = []
            for user in users:
                profile_value = None
                if hasattr(user, 'profile_photo') and user.profile_photo:
                    try:
                        profile_value = request.build_absolute_uri(
                            user.profile_photo.url)
                    except ValueError:
                        profile_value = None
                user_data.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'profile_photo': profile_value
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


class CheckAdminView(APIView):
    permission_classes = [IsOwnerOfShop]

    def get(self, request, *args, **kwargs):
        user = request.user
        return Response({"isAdmin": user.is_staff})


class ShopMetricsView(APIView):
    def get(self, request, shop_id):
        shop = get_object_or_404(Shop, shope_id=shop_id)
        today = timezone.now().date()
        first_day_this_month = today.replace(day=1)
        first_day_last_month = (first_day_this_month -
                                timedelta(days=1)).replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)

        first_day_this_month = timezone.make_aware(
            datetime.combine(first_day_this_month, datetime.min.time()))
        last_day_last_month = timezone.make_aware(
            datetime.combine(last_day_last_month, datetime.min.time()))

        revenue_this_month = Order.objects.filter(
            shop=shop,
            created_at__gte=first_day_this_month
        ).aggregate(total=Sum('total'))['total'] or 0

        revenue_last_month = Order.objects.filter(
            shop=shop,
            created_at__gte=first_day_last_month,
            created_at__lte=last_day_last_month
        ).aggregate(total=Sum('total'))['total'] or 0

        orders_this_month = Order.objects.filter(
            shop=shop,
            created_at__gte=first_day_this_month
        ).count()

        orders_last_month = Order.objects.filter(
            shop=shop,
            created_at__gte=first_day_last_month,
            created_at__lte=last_day_last_month
        ).count()

        customers_this_month = User.objects.filter(
            shop=shop,
            created_at__gte=first_day_this_month
        ).count()

        customers_last_month = User.objects.filter(
            shop=shop,
            created_at__gte=first_day_last_month,
            created_at__lte=last_day_last_month
        ).count()

        products_this_month = Products.objects.filter(
            shop=shop,
            created_at__gte=first_day_this_month
        ).count()

        products_last_month = Products.objects.filter(
            shop=shop,
            created_at__gte=first_day_last_month,
            created_at__lte=last_day_last_month
        ).count()

        return Response({
            "revenue": {"current": revenue_this_month, "previous": revenue_last_month},
            "orders": {"current": orders_this_month, "previous": orders_last_month},
            "customers": {"current": customers_this_month, "previous": customers_last_month},
            "products": {"current": products_this_month, "previous": products_last_month},
        })


class RevenueHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, shop_id):
        shop = Shop.objects.get(shope_id=shop_id)
        today = timezone.now().date()
        chart_data = []

        for i in range(6, 0, -1):
            month_start = (today.replace(day=1) -
                           timedelta(days=30 * i)).replace(day=1)
            month_end = (month_start + timedelta(days=31)).replace(day=1)

            month_start = timezone.make_aware(
                datetime.combine(month_start, datetime.min.time()))
            month_end = timezone.make_aware(
                datetime.combine(month_end, datetime.min.time()))
            revenue = (
                Order.objects.filter(
                    shop=shop,
                    status="paid",
                    created_at__gte=month_start,
                    created_at__lt=month_end,
                ).aggregate(total=Sum("total"))["total"]
                or 0
            )
            chart_data.append(
                {
                    "month": month_start.strftime("%B"),
                    "amount": float(revenue),
                }
            )

        return Response({"revenueHistory": chart_data})


class EditProductView(UpdateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsOwnerOfShop]
    lookup_field = 'pk'

    def get_object(self):
        shop_id = self.kwargs.get('shop_id')
        pk = self.kwargs.get('pk')
        return get_object_or_404(Products, pk=pk, shop__shope_id=shop_id)


class RemoveProductView(DestroyAPIView):
    permission_classes = [IsOwnerOfShop]
    lookup_field = 'pk'

    def get_object(self):
        shop_id = self.kwargs.get('shop_id')
        pk = self.kwargs.get('pk')
        return get_object_or_404(Products, pk=pk, shop__shope_id=shop_id)

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        product.delete()
        return Response({"message": "Product removed successfully"}, status=status.HTTP_204_NO_CONTENT)
