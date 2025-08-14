from django.urls import path
from .views import *

urlpatterns = [
    path('<str:shop_id>/list-product/', ListProducts.as_view(), name='listproducts'),
    path('<str:shop_id>/product-detail/<int:pk>/', DetailProduct.as_view(), name='detailproduct'),
    path('<str:shop_id>/search/<str:q>/', SearchProduct.as_view(), name='searchproduct'),
    path('<str:shop_id>/list-product-by-category/<str:category>/', ListProductsByCategory.as_view(), name='listproductsbycategory'),
    path('<str:shop_id>/product-feedback/<int:product_id>/', ProductFeedbackView.as_view(), name='productfeedback'),
    path('<str:shop_id>/feedback/', ShopFeedbackView.as_view(), name='shopfeedback'),
    path('<str:shop_id>/feedback-detail/<int:pk>/', FeedbackDetailView.as_view(), name='feedbackdetail'),
    path('<str:shop_id>/feedback-list/', FeedbackListView.as_view(), name='feedbacklist'),
    path('<str:shop_id>/add-whish', AddToWishlistView.as_view(), name='add_whish'),
    path('<str:shop_id>/wishlist/', WhishlistListView.as_view(), name='wishlistlist'),
    path('<str:shop_id>/wishlist/<int:pk>/', WhishlistDetailView.as_view(), name='wishlistdetail'),
    path('<str:shop_id>/add-to-cart/', AddToCartView.as_view(), name='add_to_cart'),
    path('<str:shop_id>/place-order/', PlaceOrderView.as_view(), name='place_order'),
    path('<str:shop_id>/cart-list/', ListCartView.as_view(), name='cartlist'),
    path('<str:shop_id>/order-detail/<int:pk>/', OrderDetailView.as_view(), name='orderdetail'),
    path('<str:shop_id>/order-list/', OrderList.as_view(), name='orderlist'),
    path('<str:shop_id>/order-single-product/', OrderSingleProductView.as_view(), name='ordersingleproduct'),
    path('<str:shop_id>/adress-detail/<int:pk>/', AdressDetailView.as_view(), name='addressdetail'),
    path('<str:shop_id>/adress-list/', AdreessListView.as_view(), name='addresslist'),
    path('<str:shop_id>/create-adress/', AdressCreateView.as_view(), name='create_address'),
]
