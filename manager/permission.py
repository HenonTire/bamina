from rest_framework.permissions import BasePermission
from .models import ShopOwner, Shop
class IsOwnerOfShop(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        shop_id = view.kwargs.get('shop_id')
        if not shop_id:
            return False

        # Check if shop exists first
        if not Shop.objects.filter(shope_id=shop_id).exists():
            # Let view handle shop not found errors
            return True

        # Now check ownership
        return ShopOwner.objects.filter(
            user=request.user,
            shop__shope_id=shop_id
        ).exists()
