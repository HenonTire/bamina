from django.shortcuts import render
from .models import Shop
from .serializer import ShopeSerializer
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView
from rest_framework.response import Response
from api.models import Products
from api.serializer import ProductSerializer
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class RegisterShopeView(CreateAPIView):
    queryset = Shop.objects.all()
    serializer_class = ShopeSerializer

class CreateProduct(CreateAPIView):
    serializer_class = ProductSerializer
    queryset = Products.objects.all()
    permission_classes = [IsAdminUser]


    def perform_create(self, serializer):
        shop_id = self.kwargs.get('shop_id')
        try:
            shop = Shop.objects.get(shope_id=shop_id)  # or id=shop_id if using default PK
            serializer.save(shop=shop)
        except Shop.DoesNotExist:
            raise serializers.ValidationError("Shop does not exist.")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['shop_id'] = self.kwargs.get('shop_id')
        return context

