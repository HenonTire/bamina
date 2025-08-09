from . import views
from django.urls import path
from .views import RegisterView, UpdateUserView, CustomTokenObtainView, LogoutView, GoogleLoginView
from .tokens import CustomTokenObtainPairView, CustomTokenRefreshView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.views import (
    TokenVerifyView
)

urlpatterns = [
    path('<str:shope_id>/register/', RegisterView.as_view(), name='register'),
    path('<str:shope_id>/update/<int:pk>/', UpdateUserView.as_view(), name='update_user')
    path('<str:shope_id>/update/<int:id>/', UpdateUserView.as_view(), name='update_user'),
    path('<str:shope_id>/login/', CustomTokenObtainView.as_view(), name='custom_token_obtain'),
    path('<str:shope_id>/logout/', LogoutView.as_view(), name='logout'),
    path('google-login/', GoogleLoginView.as_view(), name='google_login'),
    path("token/", CustomTokenObtainPairView.as_view(),name='token-obtain-pair'),
    path("token/refresh/",CustomTokenRefreshView.as_view(), name='token-refresh'),
    path("token/verify/", TokenVerifyView.as_view(), name='token-verify'),
]
