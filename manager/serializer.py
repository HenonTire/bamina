from rest_framework.serializers import ModelSerializer
from .models import Shop
from rest_framework import serializers

class ShopeSerializer(serializers.ModelSerializer):
    shope_id = serializers.CharField(read_only=True)

    class Meta:
        model = Shop
        fields = ['id', 'name', 'shope_id']  # include all needed fields

