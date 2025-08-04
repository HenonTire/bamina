from django.db import models
import uuid
from django.utils.text import slugify
from django.db import models

class Shop(models.Model):
    name = models.CharField(max_length=255)
    shope_id = models.SlugField(unique=True)
    description  = models.TextField(max_length=100, blank=True, null=True)  # could be the subdomain or slug
    def save(self, *args, **kwargs):
        if not self.shope_id:
            # Generate a slug from the name with a unique suffix
            base_slug = slugify(self.name)
            unique_suffix = uuid.uuid4().hex[:6]
            self.shope_id = f"{base_slug}-{unique_suffix}"
        super().save(*args, **kwargs)