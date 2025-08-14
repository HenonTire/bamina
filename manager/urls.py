from django.urls import path
from .views import *

urlpatterns = [
    path('<slug:shop_id>/create-product/', CreateProduct.as_view(), name='create_product'),
    path('register-shope/', RegisterShopeView.as_view(), name='register_shope'),
    path('<str:shop_id>/total-revenue/', TotalRevenueView.as_view(), name='total_revenue'),
    path('<str:shop_id>/total-orders/', TotalOrderView.as_view(), name='total_orders'),
    path('<str:shop_id>/products/', ListShopProducts.as_view(), name='list_shop_products'),
    path('<str:shop_id>/product/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('<str:shop_id>/orders/', ListOrderView.as_view(), name='list_orders'),
    path('<str:shop_id>/orders/<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('<str:shop_id>/users/', ListShopUsers.as_view(), name='list_shop_users'),
    path('<str:shop_id>/products-category/', ShopProductNumByCategory.as_view(), name='shop_product_num_by_category'),
    path('admin-login/', AdminLoginView.as_view(), name='admin_login'),
]


