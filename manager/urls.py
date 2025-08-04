from django.urls import path
from .views import *
urlpatterns = [
    path('<str:shop_id>/create-product/', CreateProduct.as_view() ),
    path('register-shope/', RegisterShopeView.as_view(), name='register_shope'),
]
