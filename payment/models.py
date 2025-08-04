from django.db import models
from django.db import models
from django.contrib.auth import get_user_model
from api.models import Order, OrderItem
User = get_user_model()

class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # Optional user reference
    chapa_tx_ref = models.CharField(max_length=100, unique=True)  # Your reference
    chapa_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='ETB')
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, null=True, blank=True)  # Optional phone number
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)  # Link to Order if needed

    def __str__(self):
        return f"{self.user} - {self.chapa_tx_ref} - {self.status}"