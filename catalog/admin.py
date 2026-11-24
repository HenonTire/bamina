from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "seller", "category", "price", "stock", "status", "created_at")
    list_filter = ("status", "category", "seller")
    search_fields = ("name", "description", "seller__business_name")
    list_editable = ("price", "stock", "status")
    actions = ["activate", "hide"]

    @admin.action(description="Make selected products active")
    def activate(self, request, queryset):
        queryset.update(status=Product.Status.ACTIVE)

    @admin.action(description="Hide selected products")
    def hide(self, request, queryset):
        queryset.update(status=Product.Status.HIDDEN)