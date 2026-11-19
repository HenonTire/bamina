from rest_framework.permissions import BasePermission

from .models import SellerProfile


class IsApprovedSeller(BasePermission):
    """
    Allows access only to authenticated sellers
    whose accounts have been approved.
    """

    message = "Your seller account has not been approved yet."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        try:
            seller = user.seller_profile
        except SellerProfile.DoesNotExist:
            return False

        return (
            user.is_active
            and seller.status == SellerProfile.Status.APPROVED
            and seller.is_phone_verified
        )


class IsSellerProfileOwner(BasePermission):
    """
    Allows a seller to access only their own seller profile.
    """

    def has_object_permission(self, request, view, obj):
        return (
            request.user.is_authenticated
            and getattr(obj, "user_id", None) == request.user.id
        )