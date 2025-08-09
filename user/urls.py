from . import views
from django.urls import path
from .views import RegisterView, UpdateUserView, LogoutView, GoogleLoginView
from .tokens import CustomTokenObtainPairView, CustomTokenRefreshView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.views import (
    TokenVerifyView
)

urlpatterns = [
    path('<str:shope_id>/register/', RegisterView.as_view(), name='register'),

    path('<str:shope_id>/update/<uuid:pk>/', UpdateUserView.as_view(), name='update_user'),
   
    path('<str:shope_id>/logout/', LogoutView.as_view(), name='logout'),
    path('google-login/', GoogleLoginView.as_view(), name='google_login'),
    path('<str:shope_id>/token/', CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('<str:shope_id>/token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),

    path("token/verify/", TokenVerifyView.as_view(), name='token-verify'),
]
