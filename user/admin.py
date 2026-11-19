from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    User,
    Customer,
    SellerProfile,
    Address,
    TelegramVerificationChallenge,
    GuestCart,
    DeviceSession,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("phone",)

    list_display = (
        "phone",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "date_joined",
    )

    search_fields = (
        "phone",
        "first_name",
        "last_name",
        "email",
    )

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        (
            "Personal information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Important dates",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "phone",
        "name",
        "is_verified",
        "trust_level",
        "is_blocked",
        "created_at",
    )

    list_filter = (
        "is_verified",
        "trust_level",
        "is_blocked",
        "verification_method",
    )

    search_fields = ("phone", "name", "telegram_chat_id")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "business_name",
        "phone",
        "status",
        "is_phone_verified",
        "created_at",
    )

    list_filter = (
        "status",
        "is_phone_verified",
    )

    search_fields = (
        "business_name",
        "phone",
        "user__first_name",
        "user__last_name",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    actions = ["approve_sellers"]

    @admin.action(description="Approve selected sellers")
    def approve_sellers(self, request, queryset):
        from django.utils import timezone

        updated = queryset.update(
            status=SellerProfile.Status.APPROVED,
            approved_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{updated} seller account(s) approved.",
        )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "customer",
        "town",
        "area",
        "delivery_phone",
        "is_default",
    )

    search_fields = (
        "customer__phone",
        "town",
        "area",
        "delivery_phone",
    )

    list_filter = ("town", "is_default")
    readonly_fields = ("id", "created_at")


@admin.register(TelegramVerificationChallenge)
class TelegramVerificationChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "phone",
        "purpose",
        "expires_at",
        "is_used",
        "created_at",
    )

    list_filter = ("purpose", "is_used")
    search_fields = ("phone",)
    readonly_fields = ("id", "token_hash", "created_at")


@admin.register(GuestCart)
class GuestCartAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "expires_at",
        "created_at",
        "updated_at",
    )

    readonly_fields = (
        "id",
        "token_hash",
        "created_at",
        "updated_at",
    )


@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "device_name",
        "last_ip",
        "is_revoked",
        "last_active",
        "expires_at",
    )

    list_filter = ("is_revoked", "device_type")
    search_fields = ("user__phone", "device_name", "last_ip")

    readonly_fields = (
        "id",
        "jti",
        "created_at",
        "last_active",
    )