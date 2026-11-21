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

        read_only_fields = fields


# =========================================================
# SELLER PROFILE
# =========================================================

class SellerProfileSerializer(serializers.ModelSerializer):

    phone = serializers.CharField(source="user.phone", read_only=True)

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