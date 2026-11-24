from django.db.models import Q
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from user.models import SellerProfile

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


def public_products():
    """Only active products from approved sellers are visible to the public."""
    return (
        Product.objects.filter(
            status=Product.Status.ACTIVE,
            seller__status=SellerProfile.Status.APPROVED,
        )
        .select_related("seller", "category")
    )


class PublicView:
    permission_classes = [AllowAny]
    authentication_classes = []


class CategoryListView(PublicView, ListAPIView):
    serializer_class = CategorySerializer
    pagination_class = None
    queryset = Category.objects.filter(is_active=True)


class ProductListView(PublicView, ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = public_products()
        params = self.request.query_params

        category = params.get("category")
        if category:
            qs = qs.filter(category__slug=category)

        q = params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        seller = params.get("seller")
        if seller:
            qs = qs.filter(seller_id=seller)

        return qs


class ProductDetailView(PublicView, RetrieveAPIView):
    serializer_class = ProductSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return public_products()