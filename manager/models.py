from django.db import models
from django.conf import settings
import uuid
from django.utils.text import slugify

class Shop(models.Model):
    name = models.CharField(max_length=255)
    shope_id = models.SlugField(unique=True)
    description = models.TextField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_marketplace = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.shope_id:
            base_slug = slugify(self.name)
            unique_suffix = uuid.uuid4().hex[:6]
            self.shope_id = f"{base_slug}-{unique_suffix}"
        super().save(*args, **kwargs)

class ShopOwner(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='admins')

    def __str__(self):
        return f"{self.user.username} - {self.shop.name}"
