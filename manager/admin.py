from django.contrib import admin

# Register your models here.
from .models import Shop, ShopOwner


admin.site.register(ShopOwner)