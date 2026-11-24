import hmac

from django.db.models import Q
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from user.models import Customer, SellerProfile, hash_secret_token
from user.permissions import IsApprovedSeller
from user.views import client_ip

from . import services
from .auth import OptionalJWTAuthentication
from .models import DeliveryZone, Order, OrderItem
from .serializers import (
    DeliveryZoneSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    SellerItemSerializer,
)


def order_queryset():
    return Order.objects.prefetch_related("items", "history")


# =========================================================
# PUBLIC / GUEST
# =========================================================

class OrderCreateView(APIView):
    """Guest or logged-in checkout: phone + address + items."""

    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]
    throttle_scope = "order_create"

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            order, raw_token = services.create_order(
                data,
                user=request.user,
                ip=client_ip(request),
                device_id=data.get("device_id", ""),
            )
        except services.OrderError as exc:
            return Response({"detail": exc.message}, status=exc.status)

        return Response(
            {
                "code": order.code,
                "status": order.status,
                "total": order.total,
                "needs_confirmation_call": order.needs_confirmation_call,
                # shown ONCE: the link that lets this person track the order
                "tracking_token": raw_token,
                "tracking_path": f"/track/{order.code}?t={raw_token}",
            },
            status=201,
        )


class OrderTrackView(APIView):
    """Order status by secret link. The phone number alone never works."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "track"

    def get(self, request, code):
        token = request.query_params.get("t", "")
        order = order_queryset().filter(code=code.upper()).first()

        if (
            not order
            or not token
            or not hmac.compare_digest(order.tracking_token_hash, hash_secret_token(token))
        ):
            return Response({"detail": "Order not found."}, status=404)

        return Response(OrderDetailSerializer(order).data)


class DeliveryZoneListView(ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = DeliveryZoneSerializer
    pagination_class = None
    queryset = DeliveryZone.objects.filter(is_active=True)


# =========================================================
# CUSTOMER (logged in)
# =========================================================

def my_orders(user):
    q = Q(placed_by=user)

    customer = Customer.objects.filter(user=user).first()
    # guest orders on this phone only appear once the phone is verified
    if customer and customer.is_verified:
        q |= Q(customer=customer)

    return order_queryset().filter(q).distinct()


class MyOrdersView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderDetailSerializer

    def get_queryset(self):
        return my_orders(self.request.user)


class MyOrderCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, code):
        order = my_orders(request.user).filter(code=code.upper()).first()

        if not order:
            return Response({"detail": "Order not found."}, status=404)

        if order.status != Order.Status.PENDING:
            return Response(
                {"detail": "Only orders waiting for confirmation can be cancelled here. Please call us."},
                status=400,
            )

        try:
            order = services.change_status(
                order, Order.Status.CANCELLED, by=request.user, note="Cancelled by customer"
            )
        except services.OrderError as exc:
            return Response({"detail": exc.message}, status=exc.status)

        return Response(OrderDetailSerializer(order).data)


# =========================================================
# SELLER (approved sellers only)
# =========================================================

VISIBLE_TO_SELLER = [
    Order.Status.CONFIRMED,
    Order.Status.PREPARING,
    Order.Status.OUT_FOR_DELIVERY,
    Order.Status.DELIVERED,
]


def seller_items(user):
    profile = SellerProfile.objects.get(user=user)

    # sellers see only items from orders Bami has confirmed, never customer contact details
    return (
        OrderItem.objects.filter(seller=profile, order__status__in=VISIBLE_TO_SELLER)
        .select_related("order")
        .order_by("-order__created_at")
    )


class SellerItemsView(ListAPIView):
    permission_classes = [IsApprovedSeller]
    serializer_class = SellerItemSerializer

    def get_queryset(self):
        qs = seller_items(self.request.user)

        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)

        return qs


class SellerItemReadyView(APIView):
    permission_classes = [IsApprovedSeller]

    def post(self, request, pk):
        item = seller_items(request.user).filter(
            pk=pk,
            order__status__in=[Order.Status.CONFIRMED, Order.Status.PREPARING],
        ).first()

        if not item:
            return Response({"detail": "Item not found."}, status=404)

        if item.status != OrderItem.Status.PENDING:
            return Response({"detail": "Item is already marked."}, status=400)

        item.status = OrderItem.Status.READY
        item.save(update_fields=["status"])

        return Response(SellerItemSerializer(item).data)