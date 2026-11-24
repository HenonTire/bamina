import uuid

from cloudinary.models import CloudinaryField
from django.db import models
from django.utils.text import slugify

from user.models import SellerProfile


class Category(models.Model):

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        HIDDEN = "hidden", "Hidden"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.PROTECT,
        related_name="products",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField(blank=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)

    # None = unlimited / not tracked
    stock = models.PositiveIntegerField(null=True, blank=True)

    image = CloudinaryField("image", folder="bami_v02/products", null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f"{slugify(self.name)[:200]}-{uuid.uuid4().hex[:6]}"
        super().save(*args, **kwargs)

    @property
    def in_stock(self):
        return self.stock is None or self.stock > 0

    def __str__(self):
        return self.name