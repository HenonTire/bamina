from django.urls import path
from .views import Registerview, UpdateUserView, CustomTokenObtainView, LogoutView  
urlpatterns = [
    path('<str:shope_id>/register/', Registerview.as_view(), name='register'),
    path('<str:shope_id>/update/<int:pk>/', UpdateUserView.as_view(), name='update_user'),
    path('<str:shope_id>/login/', CustomTokenObtainView.as_view(), name='custom_token_obtain'),
    path('<str:shope_id>/logout/', LogoutView.as_view(), name='logout'),
]
