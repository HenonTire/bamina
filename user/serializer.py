from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
User = get_user_model()
# user/serializer.py
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'shop', 'profile_photo']
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False, 'allow_blank': True}
        }

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.shop = validated_data.get('shop', instance.shop)

        password = validated_data.get('password')
        if password:
            instance.set_password(password)

        instance.save()
        return instance

    def validate_email(self, value):
        user = self.instance
        if User.objects.filter(email=value).exclude(pk=user.pk if user else None).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value
