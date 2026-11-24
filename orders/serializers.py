from rest_framework import serializers

from user.models import normalize_ethiopian_phone

from .models import DeliveryZone, Order, OrderItem


def _phone(value):
    try:
        return normalize_ethiopian_phone(value)
    except ValueError as exc:
        raise serializers.ValidationError(str(exc))


# =========================================================
# INPUT
# =========================================================

class OrderLineInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=20)


class OrderCreateSerializer(serializers.Serializer):

    name = serializers.CharField(max_length=150)
    phone = serializers.CharField()
    delivery_phone = serializers.CharField(required=False, allow_blank=True, default="")

    town = serializers.CharField(max_length=100, default="Hossaina")
    area = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    landmark = serializers.CharField(max_length=255)
    latitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, required=False, allow_null=True, default=None
    )
    longitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, required=False, allow_null=True, default=None
    )
    delivery_note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    zone_id = serializers.IntegerField(required=False, allow_null=True, default=None)

    device_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")

    items = OrderLineInputSerializer(many=True, allow_empty=False, max_length=20)

    def validate_phone(self, value):
        return _phone(value)

    def validate_delivery_phone(self, value):
        return _phone(value) if value else ""


# =========================================================
# OUTPUT
# =========================================================

class OrderItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = OrderItem
        fields = ["product_name", "unit_price", "quantity", "line_total", "status"]
        read_only_fields = fields


class OrderDetailSerializer(serializers.ModelSerializer):

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    timeline = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "code",
            "status",
            "status_display",
            "payment_method",
            "subtotal",
            "delivery_fee",
            "total",
            "town",
            "area",
            "landmark",
            "needs_confirmation_call",
            "created_at",
            "items",
            "timeline",
        ]
        read_only_fields = fields

    def get_timeline(self, obj):
        # staff notes are never exposed
        return [
            {"status": h.to_status, "at": h.created_at}
            for h in obj.history.all()
        ]


class DeliveryZoneSerializer(serializers.ModelSerializer):

    class Meta:
        model = DeliveryZone
        fields = ["id", "name", "fee"]


class SellerItemSerializer(serializers.ModelSerializer):

    order_code = serializers.CharField(source="order.code", read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)
    ordered_at = serializers.DateTimeField(source="order.created_at", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "order_code",
            "order_status",
            "ordered_at",
            "product_name",
            "unit_price",
            "quantity",
            "line_total",
            "status",
        ]
        read_only_fields = fields