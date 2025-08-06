from django.urls import path
from .views import *
urlpatterns = [
    path('<str:shop_id>/list-product/', ListProducts.as_view()),
    path('<str:shop_id>/product-detail/<int:pk>/', DetailProduct.as_view()),
    path('<str:shop_id>/search/<str:q>/', SearchProduct.as_view()),
    path('<str:shop_id>/list-product-by-category/<str:category>/', ListProductsByCategory.as_view()),
    path('<str:shop_id>/product-feedback/<int:product_id>/', ProductFeedbackView.as_view()),
    path('<str:shop_id>/feedback/', ShopFeedbackView.as_view()),
    path('<str:shop_id>/feedback-detail/<int:pk>/', FeedbackDetailView.as_view()),
    path('<str:shop_id>/feedback-list/', FeedbackListView.as_view()),
    path('<str:shop_id>/add-whish', AddToWishlistView.as_view()),
    path('<str:shop_id>/wishlist/', WhishlistListView.as_view()),
    path('<str:shop_id>/wishlist/<int:pk>/', WhishlistDetailView.as_view()),
    path('<str:shop_id>/add-to-cart/', AddToCartView.as_view()),
    path('<str:shop_id>/place-order/', PlaceOrderView.as_view()),
    path('<str:shop_id>/cart-list/', ListCartView.as_view()),
    path('<str:shop_id>/order-detail/<int:pk>/', OrderDetailView.as_view()),
    path('<str:shop_id>/order-list/', OrderList.as_view()),
    path('<str:shop_id>/order-single-product/', OrderSingleProductView.as_view()),
    path('<str:shop_id>/adress-detail/<int:pk>/', AdressDetailView.as_view()),
    path('<str:shop_id>/adress-list/', AdreessListView.as_view()),
    path('<str:shop_id>/create-adress/', AdressCreateView.as_view()),

]

