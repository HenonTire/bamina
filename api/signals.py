from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from .models import Products, ProductVariant, Inventory


@receiver(post_save, sender=Products)
def create_default_variant_and_inventory(
    sender,
    instance,
    created,
    **kwargs,
):
    if not created:
        return

    # Don't create another variant if one already exists
    if instance.variants.exists():
        return

    sku = f'{slugify(instance.name)[:80] or "product"}-{instance.pk}'

    variant = ProductVariant.objects.create(
        product=instance,
        name='Default',
        sku=sku,
        price=instance.price,
    )

    Inventory.objects.create(
        variant=variant,
        quantity_available=1,
    )