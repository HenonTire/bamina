from django.contrib import admin

# Register your models here.
from .models import *
admin.site.register(WhishList)
admin.site.register(Products)
admin.site.register(ProdyctFeedback)
admin.site.register(ShopFeedBack)
admin.site.register(CartItem)
# admin.site.register(OrderItem)  # Uncomment if OrderItem model is defined and registere
admin.site.register(Order)
admin.site.register(OrderItem)  # Uncomment if OrderItem model is defined and registered
from manager.models import Shop
admin.site.register(Shop)  # Register the Shop model if it's not already registered