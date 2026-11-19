from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers

from .models import (
    User,
    Customer,
    SellerProfile,
    Address,
    normalize_ethiopian_phone,
)


# =========================================================
# PHONE VALIDATION
# =========================================================

class PhoneValidationMixin:

    def validate_phone(self, value):
        try:
            return normalize_ethiopian_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))


# =========================================================
# BUYER REGISTRATION
# =========================================================

class BuyerRegistrationSerializer(
    PhoneValidationMixin,
    serializers.ModelSerializer,
):

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "first_name",
            "last_name",
            "email",
            "password",
        ]

        read_only_fields = ["id"]

    @transaction.atomic
    def create(self, validated_data):

        password = validated_data.pop("password")

        user = User.objects.create_user(
            password=password,
            **validated_data,
        )

        Customer.objects.create(
            user=user,
            phone=user.phone,
            name=f"{user.first_name} {user.last_name}".strip(),
        )

        return user


# =========================================================
# SELLER REGISTRATION
# =========================================================

class SellerRegistrationSerializer(
    PhoneValidationMixin,
    serializers.ModelSerializer,
):

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )

    business_name = serializers.CharField(
        write_only=True,
        max_length=200,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "first_name",
            "last_name",
            "email",
            "password",
            "business_name",
        ]

        read_only_fields = ["id"]

    @transaction.atomic
    def create(self, validated_data):

        password = validated_data.pop("password")
        business_name = validated_data.pop("business_name")

        user = User.objects.create_user(
            password=password,
            **validated_data,
        )

        SellerProfile.objects.create(
            user=user,
            phone=user.phone,
            business_name=business_name,
            status=SellerProfile.Status.PENDING,
        )

        return user


# =========================================================
# LOGIN
# =========================================================

class LoginSerializer(PhoneValidationMixin, serializers.Serializer):

    phone = serializers.CharField()

    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):

        phone = attrs.get("phone")
        password = attrs.get("password")

        request = self.context.get("request")

        user = authenticate(
            request=request,
            phone=phone,
            password=password,
        )

        if not user:
            raise serializers.ValidationError(
                "Invalid phone number or password."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "This account is inactive."
            )

        attrs["user"] = user

        return attrs


# =========================================================
# USER PROFILE
# =========================================================

class UserProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "first_name",
            "last_name",
            "email",
            "date_joined",
        ]

        read_only_fields = [
            "id",
            "phone",
            "date_joined",
        ]


# =========================================================
# CUSTOMER PROFILE
# =========================================================

class CustomerProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "phone",
            "is_verified",
            "verification_method",
            "trust_level",
        ]

        read_only_fields = [
            "id",
            "phone",
            "is_verified",
            "verification_method",
            "trust_level",
        ]


# =========================================================
# SELLER PROFILE
# =========================================================

class SellerProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = SellerProfile
        fields = [
            "id",
            "business_name",
            "phone",
            "status",
            "is_phone_verified",
            "approved_at",
            "created_at",
        ]

        read_only_fields = fields


# =========================================================
# ADDRESS
# =========================================================

class AddressSerializer(serializers.ModelSerializer):

    class Meta:
        model = Address
        fields = [
            "id",
            "town",
            "area",
            "kebele",
            "landmark",
            "latitude",
            "longitude",
            "delivery_phone",
            "delivery_note",
            "is_default",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_delivery_phone(self, value):

        try:
            return normalize_ethiopian_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

    def create(self, validated_data):

        customer = self.context.get("customer")

        if not customer:
            raise serializers.ValidationError(
                "Customer context is required."
            )

        return Address.objects.create(
            customer=customer,
            **validated_data,
        )

    def update(self, instance, validated_data):

        validated_data.pop("customer", None)

        return super().update(instance, validated_data)