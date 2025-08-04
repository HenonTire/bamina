from django.shortcuts import render
from .models import *
from .serializer import *
from rest_framework.generics import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

class ListProducts(ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        return Products.objects.filter(shop__shope_id=shop_id)

class DetailProduct(RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    queryset = Products.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def get_object(self):
        shope_id = self.kwargs.get('shop_id')
        pk = self.kwargs.get('pk')
        return get_object_or_404(Products, pk=pk, shop__shope_id=shope_id)



class SearchProduct(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, q, *args, **kwargs):
        # Case-insensitive partial match on name
        shop_id = self.kwargs.get('shop_id')
        result = Products.objects.filter(name__icontains=q ,shop__shope_id=shop_id)
        serializer = ProductSerializer(result, many=True)
        return Response(serializer.data)
    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        return Products.objects.filter(shop__shope_id=shop_id)
    
class ListProductsByCategory(ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        category = self.kwargs.get('category')
        return Products.objects.filter(shop__shope_id=shop_id, category=category)
    
class ProductFeedbackView(CreateAPIView):
    serializer_class = ProductFeedbackSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Products, id=product_id, shop__shope_id=self.kwargs.get('shop_id'))
        serializer.save(product=product, user=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    

class ShopFeedbackView(CreateAPIView):
    serializer_class = ShopFeedBackSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        shop_id = self.kwargs.get('shop_id')
        shop = get_object_or_404(Shop, shope_id=shop_id)
        serializer.save(shop=shop, user=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
class FeedbackDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = ShopFeedBackSerializer
    permission_classes = [IsAuthenticated]
    queryset = ShopFeedBack.objects.all()
    lookup_field = 'pk'

    def get_object(self):
        shop_id = self.kwargs.get('shop_id')
        pk = self.kwargs.get('pk')
        return get_object_or_404(ShopFeedBack, pk=pk, shop__shope_id=shop_id)
class FeedbackListView(ListAPIView):
    serializer_class = ShopFeedBackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        return ShopFeedBack.objects.filter(shop__shope_id=shop_id)  
class AddToWishlistView(CreateAPIView):
    serializer_class = WhishlistSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        product_id = self.request.data.get('product_id')
        product = get_object_or_404(Products, id=product_id, shop__shope_id=self.kwargs.get('shop_id'))
        wishlist = serializer.save(user=self.request.user)
        wishlist.products.add(product)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
class WhishlistListView(ListAPIView):
    serializer_class = WhishlistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')  # or 'shop_id' depending on URL
        return WhishList.objects.filter(
            user=self.request.user,
            products__shop__shope_id=shop_id
        ).distinct()


class WhishlistDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = WhishlistSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def get_object(self):
        shop_id = self.kwargs.get('shop_id')
        return get_object_or_404(
            WhishList,
            pk=self.kwargs.get('pk'),
            user=self.request.user,
            products__shop__shope_id=shop_id
        )


class AddToCartView(CreateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        product_id = self.request.data.get('product_id')
        product = get_object_or_404(Products, id=product_id, shop__shope_id=self.kwargs.get('shop_id'))
        cart_item, created = CartItem.objects.get_or_create(user=self.request.user, product=product)
       
        cart_item.save()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
from rest_framework.exceptions import ValidationError

class PlaceOrderView(CreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()

    def perform_create(self, serializer):
        cart_items = CartItem.objects.filter(user=self.request.user)

        if not cart_items.exists():
            raise ValidationError("Your cart is empty")

        total_price = sum(item.get_total_price() for item in cart_items)

        order = serializer.save(user=self.request.user, total=total_price)

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )

        cart_items.delete()
        return order

class ListCartView(ListAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user)