from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("register", views.RegisterView.as_view()),
    path("login", views.LoginView.as_view()),
    path("refresh", TokenRefreshView.as_view()),
    path("logout", views.LogoutView.as_view()),
    path("me", views.MeView.as_view()),

    path("telegram/link/start", views.TelegramLinkStartView.as_view()),
    path("telegram/link/complete", views.TelegramLinkCompleteView.as_view()),
    path("telegram/webhook", views.TelegramWebhookView.as_view()),

    path("password/reset/request", views.ResetRequestView.as_view()),
    path("password/reset/confirm", views.ResetConfirmView.as_view()),
]