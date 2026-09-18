from django.shortcuts import render
from decimal import Decimal
from uuid import uuid4

from .models import *
from .serializer import *

from rest_framework.generics import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework import status

from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework.exceptions import ValidationError
from rest_framework.exceptions import NotFound

from .utils import send_fcm_notification

from manager.models import ShopOwner
from manager.permission import IsSeller

from .services import (
    add_to_cart,
    checkout,
    collect_cod,
    create_settlements,
    get_cart,
    get_or_create_variant,
    marketplace_shop,
    remove_cart_item,
    transition_delivery,
    transition_order,
    transition_product,
    update_cart_item,
)

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
            Products,
            id=product_id,
            shop__shope_id=self.kwargs.get('shop_id'),
        )

        # Get or create the new central cart
        cart = get_cart(self.request.user)

        # Get the product's active variant.
        variant = get_or_create_variant(product)

        if not variant.is_active:
            raise ValidationError(
                "This product is not available."
            )

        # Make sure the product is approved
        if product.status != Products.Status.APPROVED:
            raise ValidationError(
                "This product is not available."
            )

        # Check inventory
        inventory = Inventory.objects.get(
            variant=variant
        )

        if inventory.available_quantity <= 0:
            raise ValidationError(
                "This product is out of stock."
            )

        # Check if this product/variant is already in cart
        cart_item = CartItem.objects.filter(
            cart=cart,
            variant=variant,
        ).first()

        if cart_item:
            raise ValidationError(
                "Product already in cart"
            )

        # Create the new-format cart item
        cart_item = CartItem.objects.create(
            cart=cart,
            user=self.request.user,
            product=product,
            variant=variant,
            quantity=1,
            unit_price=variant.price,
        )

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

    def create(self, request, *args, **kwargs):
        shipping_address_id = request.data.get("shipping_address_id")

        if shipping_address_id:
            shipping_address = get_object_or_404(
                Adress,
                id=shipping_address_id,
                user=request.user,
            )
        else:
            legacy_address = request.data.get("shipping_address")

            if not legacy_address:
                raise ValidationError(
                    "Shipping address is required"
                )

            shipping_address = Adress.objects.create(
                user=request.user,
                address=legacy_address,
            )

        # Keep compatibility with the old frontend.
        # The frontend may not send an idempotency key.
        idempotency_key = (
            request.data.get("idempotency_key")
            or str(uuid4())
        )

        delivery_fee = request.data.get(
            "delivery_fee",
            Decimal("100"),
        )

        notes = request.data.get(
            "notes",
            "",
        )

        order = checkout(
            user=request.user,
            shipping_address=shipping_address,
            idempotency_key=idempotency_key,
            delivery_fee=delivery_fee,
            notes=notes,
        )

        serializer = self.get_serializer(order)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


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
        if shipping_address_id:
            shipping_address = get_object_or_404(
                Adress, id=shipping_address_id, user=request.user)
        else:
            legacy_address = request.data.get('shipping_address')
            if not legacy_address:
                return Response({"error": "Shipping address is required"}, status=400)
            shipping_address = Adress.objects.create(user=request.user, address=legacy_address)
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

        shop_owner = ShopOwner.objects.filter(shop=shop).first()
        if shop_owner:
            try:
                send_fcm_notification(
                    user=shop_owner.user,
                    shop=shop,
                    title="New Order Placed",
                    body=f"{request.user.username} just placed an order with total {product.price}",
                )
            except Exception as e:
                print("Failed to send FCM:", str(e))

        serializer = OrderSerializer(order)
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


class CoreProductListView(ListAPIView):
    serializer_class = CoreProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        shop = marketplace_shop()
        queryset = Products.objects.filter(status=Products.Status.APPROVED)
        if shop:
            queryset = queryset.filter(shop=shop)
        category = self.request.query_params.get('category')
        query = self.request.query_params.get('q')
        if category:
            queryset = queryset.filter(category=category)
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(description__icontains=query))
        return queryset.prefetch_related('variants__inventory').order_by('-created_at')


class CoreProductDetailView(RetrieveAPIView):
    serializer_class = CoreProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Products.objects.filter(status=Products.Status.APPROVED).prefetch_related('variants__inventory')


class CategoryListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        categories = Products.objects.filter(status=Products.Status.APPROVED).values_list('category', flat=True).distinct()
        return Response(sorted(value for value in categories if value))


class ProductVariantListView(ListAPIView):
    serializer_class = VariantSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return ProductVariant.objects.filter(product_id=self.kwargs['product_id'], product__status=Products.Status.APPROVED, is_active=True)


class CoreCartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart = get_cart(request.user)
        return Response(CoreCartItemSerializer(cart.items.select_related('variant__product').all(), many=True).data)


class CoreCartItemCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = add_to_cart(request.user, **serializer.validated_data)
        return Response(CoreCartItemSerializer(item).data, status=status.HTTP_201_CREATED)


class CoreCartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = update_cart_item(request.user, pk, serializer.validated_data['quantity'])
        return Response(CoreCartItemSerializer(item).data)

    def delete(self, request, pk):
        remove_cart_item(request.user, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = get_object_or_404(Adress, pk=serializer.validated_data.pop('shipping_address_id'), user=request.user)
        key = request.headers.get('Idempotency-Key') or request.data.get('idempotency_key')
        order = checkout(request.user, address, key, **serializer.validated_data)
        return Response(CoreOrderSerializer(order).data, status=status.HTTP_201_CREATED)


class CoreOrderListView(ListAPIView):
    serializer_class = CoreOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items', 'payment', 'delivery').order_by('-created_at')


class CoreOrderDetailView(RetrieveAPIView):
    serializer_class = CoreOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items', 'payment', 'delivery')


class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, user=request.user)
        order = transition_order(order, OrderStatus.CANCELLED)
        return Response(CoreOrderSerializer(order).data)


class CoreAddressListView(ListCreateAPIView):
    serializer_class = CoreAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Adress.objects.filter(user=self.request.user).order_by('-is_default', '-created_at')


class CoreAddressDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = CoreAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Adress.objects.filter(user=self.request.user)


class SellerProductListView(ListCreateAPIView):
    serializer_class = SellerProductSerializer
    permission_classes = [IsSeller]

    def get_queryset(self):
        return Products.objects.filter(seller=self.request.user.seller_profile).prefetch_related('variants')

    def perform_create(self, serializer):
        shop = marketplace_shop()
        if not shop:
            raise ValidationError('The marketplace shop is not configured.')
        price = serializer.validated_data.pop('price')
        sku = serializer.validated_data.pop('sku')
        initial_stock = serializer.validated_data.pop('initial_stock')
        product = serializer.save(shop=shop, seller=self.request.user.seller_profile, status=Products.Status.DRAFT)
        variant = ProductVariant.objects.create(product=product, name='Default', sku=sku, price=price)
        Inventory.objects.create(variant=variant, quantity_available=initial_stock)


class SellerProductDetailView(RetrieveUpdateAPIView):
    serializer_class = SellerProductSerializer
    permission_classes = [IsSeller]

    def get_queryset(self):
        return Products.objects.filter(seller=self.request.user.seller_profile)

    def perform_update(self, serializer):
        product = self.get_object()
        if product.status not in {Products.Status.DRAFT, Products.Status.REJECTED}:
            raise ValidationError('Only draft or rejected products can be edited.')
        serializer.save(status=Products.Status.DRAFT)


class SellerProductSubmitView(APIView):
    permission_classes = [IsSeller]

    def post(self, request, pk):
        product = get_object_or_404(Products, pk=pk, seller=request.user.seller_profile)
        product = transition_product(product, Products.Status.PENDING_REVIEW)
        return Response(CoreProductSerializer(product).data)


class AdminProductTransitionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        product = get_object_or_404(Products, pk=pk)
        product = transition_product(product, request.data.get('status'))
        return Response(CoreProductSerializer(product).data)


class SellerOrderListView(ListAPIView):
    serializer_class = CoreOrderSerializer
    permission_classes = [IsSeller]

    def get_queryset(self):
        return Order.objects.filter(items__seller=self.request.user.seller_profile).distinct().prefetch_related('items', 'payment', 'delivery')


class SellerSettlementListView(ListAPIView):
    serializer_class = serializers.ModelSerializer
    permission_classes = [IsSeller]

    def get(self, request, *args, **kwargs):
        settlements = Settlement.objects.filter(seller=request.user.seller_profile).order_by('-created_at')
        return Response([
            {'id': item.id, 'order': item.order_id, 'amount': item.amount, 'platform_fee': item.platform_fee, 'delivery_amount': item.delivery_amount, 'status': item.status}
            for item in settlements
        ])


class AdminOrderTransitionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        order = transition_order(order, request.data.get('status'))
        return Response(CoreOrderSerializer(order).data)


class AdminDeliveryTransitionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk)
        delivery = transition_delivery(delivery, request.data.get('status'), request.data.get('failure_reason', ''))
        return Response({'id': delivery.id, 'status': delivery.status, 'order': delivery.order_id})


class AdminCollectCODView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        payment = collect_cod(payment)
        return Response({'id': payment.id, 'status': payment.status, 'collected_at': payment.collected_at})
