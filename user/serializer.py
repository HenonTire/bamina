from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
User = get_user_model()
# user/serializer.py
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {
                'write_only': True,
                'required': False,  # ✅ allow blank in partial update
                'allow_blank': True,
            }
        }

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)

        password = validated_data.get('password')
        if password:  # ✅ only update if it's actually passed
            instance.set_password(password)

        instance.save()
        return instance
    def validate_email(self, value):
    # value is the email string
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value


# class CookieTokenRefreshSerializer(TokenRefreshSerializer):
#     def validate(self, attrs):
#         request = self.context['request']
#         refresh = attrs.get('refresh') or request.COOKIES.get('refresh')
#         if not refresh:
#             raise self.fail('no_token')
#         attrs['refresh'] = refresh
#         return super().validate(attrs)