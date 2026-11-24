from django.urls import path

from . import views

urlpatterns = [
    path("categories", views.CategoryListView.as_view()),
    path("products", views.ProductListView.as_view()),
    path("products/<slug:slug>", views.ProductDetailView.as_view()),
]