from rest_framework.permissions import BasePermission
from .models import ShopOwner

class IsOwnerOfShop(BasePermission):
    """
    Allow access only if the authenticated user owns the shop in question.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        shop_id = view.kwargs.get('shop_id')  # From URL like /manage/<shop_id>/create-product/
        if not shop_id:
            return False

        return ShopOwner.objects.filter(
            user=request.user,
            shop__shope_id=shop_id
        ).exists()
