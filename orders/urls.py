from django.urls import path

from . import views

urlpatterns = [
    path("orders", views.OrderCreateView.as_view()),
    path("orders/zones", views.DeliveryZoneListView.as_view()),
    path("orders/track/<str:code>", views.OrderTrackView.as_view()),

    path("orders/mine", views.MyOrdersView.as_view()),
    path("orders/mine/<str:code>/cancel", views.MyOrderCancelView.as_view()),

    path("orders/seller/items", views.SellerItemsView.as_view()),
    path("orders/seller/items/<uuid:pk>/ready", views.SellerItemReadyView.as_view()),
]