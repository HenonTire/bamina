from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from django.utils import timezone
 
from .models import (
    Address,
    Customer,
    DeviceSession,
    SellerProfile,
    TelegramVerificationChallenge,
    User,
)
 
 
class UserCreateForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("phone",)
 
 
class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
 
 
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreateForm
    ordering = ("phone",)
    list_display = ("phone", "first_name", "is_staff", "is_active", "date_joined")
    search_fields = ("phone", "first_name", "last_name")
 
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "email")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "password1", "password2")}),
    )
 
 
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("phone", "name", "is_verified", "is_blocked", "trust_level", "created_at")
    list_filter = ("is_verified", "is_blocked", "trust_level")
    search_fields = ("phone", "name")
 
 
@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ("business_name", "seller_phone", "status", "is_phone_verified", "created_at")
    list_filter = ("status",)
    search_fields = ("business_name", "user__phone")
    actions = ["approve", "reject", "suspend"]
 
    @admin.display(description="Phone")
    def seller_phone(self, obj):
        return obj.user.phone
 
    @admin.action(description="Approve selected sellers")
    def approve(self, request, queryset):
        n = queryset.update(status=SellerProfile.Status.APPROVED, approved_at=timezone.now())
        self.message_user(request, f"{n} seller(s) approved.", messages.SUCCESS)
 
    @admin.action(description="Reject selected sellers")
    def reject(self, request, queryset):
        n = queryset.update(status=SellerProfile.Status.REJECTED)
        self.message_user(request, f"{n} seller(s) rejected.", messages.WARNING)
 
    @admin.action(description="Suspend selected sellers")
    def suspend(self, request, queryset):
        n = queryset.update(status=SellerProfile.Status.SUSPENDED)
        self.message_user(request, f"{n} seller(s) suspended.", messages.WARNING)
 
 
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("customer", "town", "area", "landmark", "is_default")
    search_fields = ("customer__phone", "landmark")
 
 
@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "device_name", "last_ip", "is_revoked", "created_at")
    list_filter = ("is_revoked",)
 
 
@admin.register(TelegramVerificationChallenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("phone", "purpose", "verified_at", "is_used", "attempts", "created_at")
    list_filter = ("purpose", "is_used")
    readonly_fields = ("token_hash",)
 