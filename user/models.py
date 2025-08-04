from django.db import models
from django.contrib.auth.models import AbstractUser
from manager.models import  Shop
# Create your models here.
class User(AbstractUser):
    profile = models.ImageField(upload_to='profile/',blank=True, null=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, blank=True, null=True)