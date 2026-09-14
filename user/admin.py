from django.contrib import admin
from .models import User, SellerProfile
admin.site.register(User)
admin.site.site_header = "Bamina Admin"
admin.site.register(SellerProfile)

# Register your models here.
