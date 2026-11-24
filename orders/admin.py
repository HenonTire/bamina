from django.contrib import admin, messages

from . import services
from .models import DeliveryZone, Order, OrderItem, OrderStatusHistory

S = Order.Status


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "seller", "product_name", "unit_price", "quantity", "line_total")
    fields = readonly_fields + ("status",)

    def has_add_permission(self, request, obj=None):
        return False


class HistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("from_status", "to_status", "changed_by", "note", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "code", "status", "needs_confirmation_call", "customer_name", "customer_phone",
        "landmark", "total", "created_at",
    )
    list_filter = ("status", "needs_confirmation_call", "zone")
    search_fields = ("code", "customer_phone", "customer_name", "delivery_phone", "landmark")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, HistoryInline]
    exclude = ("tracking_token_hash",)
    readonly_fields = (
        "code", "customer", "placed_by", "customer_name", "customer_phone", "delivery_phone",
        "town", "area", "landmark", "latitude", "longitude", "delivery_note", "zone",
        "status", "payment_method", "subtotal", "delivery_fee", "total",
        "needs_confirmation_call", "confirmed_at", "confirmed_by",
        "ip_address", "device_id", "created_at", "updated_at",
    )
    actions = [
        "mark_confirmed", "mark_preparing", "mark_out_for_delivery",
        "mark_delivered", "mark_failed", "mark_cancelled",
    ]

    def has_add_permission(self, request):
        return False

    def _move(self, request, queryset, to_status):
        done = 0
        for order in queryset:
            try:
                services.change_status(order, to_status, by=request.user, note="Changed in admin")
                done += 1
            except services.OrderError as exc:
                self.message_user(request, f"{order.code}: {exc.message}", messages.ERROR)
        if done:
            self.message_user(request, f"{done} order(s) updated.", messages.SUCCESS)

    @admin.action(description="Confirm (customer called and agreed)")
    def mark_confirmed(self, request, queryset):
        self._move(request, queryset, S.CONFIRMED)

    @admin.action(description="Seller preparing")
    def mark_preparing(self, request, queryset):
        self._move(request, queryset, S.PREPARING)

    @admin.action(description="Out for delivery")
    def mark_out_for_delivery(self, request, queryset):
        self._move(request, queryset, S.OUT_FOR_DELIVERY)

    @admin.action(description="Delivered")
    def mark_delivered(self, request, queryset):
        self._move(request, queryset, S.DELIVERED)

    @admin.action(description="Delivery failed")
    def mark_failed(self, request, queryset):
        self._move(request, queryset, S.FAILED)

    @admin.action(description="Cancel")
    def mark_cancelled(self, request, queryset):
        self._move(request, queryset, S.CANCELLED)


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "fee", "is_active")
    list_editable = ("fee", "is_active")