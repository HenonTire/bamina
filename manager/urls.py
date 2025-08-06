from django.urls import path
from .views import *
urlpatterns = [
    path('<str:shop_id>/create-product/', CreateProduct.as_view() ),
    path('register-shope/', RegisterShopeView.as_view(), name='register_shope'),
    path('<str:shop_id>/total-revenue/', TotalRevenueView.as_view(), name='total_revenue'),
    path('<str:shop_id>/total-orders/', TotalOrderView.as_view(), name='total_orders'),
    path('<str:shop_id>/products/', ListShopProducts.as_view(), ),
    path('<str:shop_id>/product/<int:pk>/', ProductDetailView.as_view(), name='list_orders'),
    path('<str:shop_id>/orders/', ListOrderView.as_view(), name='list_orders'),
    path('<str:shop_id>/orders/<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('<str:shop_id>/users/', ListShopUsers.as_view(), name='users'),
    path('<str:shop_id>/products-category', ShopProductNumByCategory.as_view(), name='user_detail'),
  
]

