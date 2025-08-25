from django.shortcuts import render
from .models import *
from .serializer import *
from rest_framework.generics import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from .utils import send_fcm_notification
from rest_framework.exceptions import NotFound
from django.shortcuts import get_object_or_404
from rest_framework import status
from manager.models import ShopOwner


class ListProducts(ListAPIView):
    serializer_class = ProductSerializer
    # we don't need users to be authenticated cause we want non-logged in users to access shop products
    permission_classes = [AllowAny]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        return Products.objects.filter(shop__shope_id=shop_id).order_by('-created_at')


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
        result = Products.objects.filter(
            name__icontains=q, shop__shope_id=shop_id)
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
        product = get_object_or_404(
            Products, id=product_id, shop__shope_id=self.kwargs.get('shop_id'))
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
        product = get_object_or_404(
            Products, id=product_id, shop__shope_id=self.kwargs.get('shop_id'))

        # Check if wishlist for user exists or create
        wishlist, created = WhishList.objects.get_or_create(
            user=self.request.user)

        # Check if product already in wishlist
        if wishlist.products.filter(id=product.id).exists():
            raise ValidationError("Product already in wishlist")

        wishlist.products.add(product)
        wishlist.save()
        serializer.instance = wishlist  # To set the instance for response

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class RemoveFromWishlistView(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        product_id = self.request.data.get('product_id')
        if not product_id:
            return Response({"error": "Product ID is required"}, status=400)

        product = get_object_or_404(
            Products,
            id=product_id,
            shop__shope_id=self.kwargs.get('shop_id')
        )

        wishlist = get_object_or_404(WhishList, user=self.request.user)

        if not wishlist.products.filter(id=product.id).exists():
            raise NotFound("Product not found in wishlist")

        wishlist.products.remove(product)
        wishlist.save()

        return Response({"message": "Product removed from wishlist"}, status=200)


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
        product = get_object_or_404(
            Products, id=product_id, shop__shope_id=self.kwargs.get('shop_id'))

        # Check if item already in cart for this user and product
        cart_item, created = CartItem.objects.get_or_create(
            user=self.request.user, product=product)
        if not created:
            raise ValidationError("Product already in cart")

        cart_item.save()
        serializer.instance = cart_item

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class RemoveFromCartView(DestroyAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        product_id = self.request.data.get('product_id')
        product = get_object_or_404(
            Products, id=product_id, shop__shope_id=self.kwargs.get('shop_id')
        )
        cart_item = get_object_or_404(
            CartItem, user=self.request.user, product=product)
        return cart_item

    def destroy(self, request, *args, **kwargs):
        cart_item = self.get_object()
        cart_item.delete()
        return Response({"detail": "Product removed from cart"}, status=status.HTTP_204_NO_CONTENT)


class PlaceOrderView(CreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()

    def perform_create(self, serializer):
        request = self.request
        shop_id = self.kwargs.get('shop_id')

        shipping_address_id = request.data.get("shipping_address_id")
        if not shipping_address_id:
            raise ValidationError("Shipping address is required")
        shipping_address = get_object_or_404(
            Adress, id=shipping_address_id, user=request.user)

        # Validate shop
        shop = get_object_or_404(Shop, shope_id=shop_id)

        # Get cart items for user and shop
        cart_items = CartItem.objects.filter(
            user=request.user, product__shop=shop)
        if not cart_items.exists():
            raise ValidationError("Your cart is empty")

        # Prepare current cart products + quantities dict
        cart_products = {}
        for item in cart_items:
            cart_products[item.product.id] = item.quantity

        # Check if active order with same products and quantities exists
        active_orders = Order.objects.filter(
            user=request.user, shop=shop, status=OrderStatus.IN_PROCESS)
        for order in active_orders:
            order_items = order.items.all()  # assuming related_name='items' for OrderItem FK
            order_products = {oi.product.id: oi.quantity for oi in order_items}

            if order_products == cart_products:
                raise ValidationError(
                    "An active order with these products already exists")

        total_price = sum(item.get_total_price() for item in cart_items)
        order = serializer.save(
            user=request.user, total=total_price, shop=shop, status=OrderStatus.IN_PROCESS, shipping_address=shipping_address)

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price,
            )

            item.product.is_sold_out = True
            item.product.save()

        # Clear the cart after order placed
        CartItem.objects.filter(
            user=request.user, product__shop=shop).delete()

        # Send notification if token provided
        shop_owner = ShopOwner.objects.filter(shop=shop).first()
        if shop_owner:
            try:
                data = send_fcm_notification(
                    user=shop_owner.user,
                    shop=shop,
                    title="🛒 New Order Placed",
                    body=f"{request.user.username} just placed an order in your shop."
                )
                print(data)
            except Exception as e:
                print("Failed to send FCM:", e)

        return order


class ListCartView(ListAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        shop = get_object_or_404(Shop, shope_id=shop_id)
        return CartItem.objects.filter(user=self.request.user, product__shop=shop)


class OrderDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def get_object(self):
        shop_id = self.kwargs.get('shop_id')
        shop = get_object_or_404(Shop, shope_id=shop_id)
        return get_object_or_404(Order, pk=self.kwargs.get('pk'), user=self.request.user, shop=shop)


class OrderSingleProductView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        shop_id = self.kwargs.get('shop_id')
        shop = get_object_or_404(Shop, shope_id=shop_id)

        product_id = request.data.get('product_id')
        product = get_object_or_404(Products, id=product_id, shop=shop)

        shipping_address_id = request.data.get("shipping_address_id")
        if not shipping_address_id:
            return Response({"error": "Shipping address is required"}, status=400)
        shipping_address = get_object_or_404(
            Adress, id=shipping_address_id, user=request.user)
        shop_fcm_token = request.data.get('shop_fcm_token')

        order = Order.objects.create(
            user=request.user,
            shop=shop,
            shipping_address=shipping_address,
            # payment_method=payment_method,
            total=product.price,
            status=OrderStatus.IN_PROCESS
        )

        OrderItem.objects.create(
            order=order, product=product, quantity=1, price=product.price)

        if shop_fcm_token:
            try:
                send_fcm_notification(
                    shop_fcm_token,
                    "🛒 New Order Placed",
                    f"{request.user.username} just placed an order with total ${product.price}"
                )
            except Exception as e:
                print("Failed to send FCM:", str(e))

        serializer = ProductSerializer(order)
        return Response(serializer.data)


class OrderList(ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        shop = get_object_or_404(Shop, shope_id=shop_id)
        return Order.objects.filter(user=self.request.user, shop=shop)


class AddressCreateView(CreateAPIView):
    serializer_class = AdressSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class AddreessListView(ListAPIView):
    serializer_class = AdressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Adress.objects.filter(user=self.request.user)


class AddressDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = AdressSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def get_object(self):
        return get_object_or_404(Adress, pk=self.kwargs.get('pk'), user=self.request.user)


class AddressRemoveView(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        address_id = request.data.get("address_id")
        if not address_id:
            return Response({"error": "Address ID is required"}, status=400)

        address = get_object_or_404(Adress, id=address_id, user=request.user)
        address.delete()

        return Response({"message": "Address removed successfully"}, status=status.HTTP_200_OK)


class AddressSetDefaultView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        address_id = request.data.get('address_id')
        if not address_id:
            return Response({"error": "Address ID is required"}, status=400)
        address = get_object_or_404(Adress, pk=address_id, user=request.user)

        # Set all other addresses to not default
        Adress.objects.filter(user=request.user).update(is_default=False)

        # Set this address as default
        address.is_default = True
        address.save()

        return Response({"message": "Address set as default successfully"})


class SaveFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, shop_id):
        token = request.data.get("token")

        if token:
            FCMToken.objects.update_or_create(
                user=request.user, token=token, shop=Shop.objects.get(shope_id=shop_id))
        return Response({"message": "Token saved"})


class AllNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, shop_id):
        notifications = Notification.objects.filter(
            user=request.user, shop_id=Shop.objects.get(shope_id=shop_id))
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)
