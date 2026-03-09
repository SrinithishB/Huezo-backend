from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    ChangePasswordView,
    MeView,
    MyCustomerProfileView,
)

urlpatterns = [

    # ------------------------------------------------------------------ #
    # AUTH
    # ------------------------------------------------------------------ #
    path("auth/register/",        RegisterView.as_view(),       name="auth-register"),
    path("auth/login/",           LoginView.as_view(),          name="auth-login"),
    path("auth/logout/",          LogoutView.as_view(),         name="auth-logout"),
    path("auth/token/refresh/",   TokenRefreshView.as_view(),   name="token-refresh"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("auth/me/",              MeView.as_view(),             name="auth-me"),

    # ------------------------------------------------------------------ #
    # CUSTOMER PROFILE  (self-service)
    # ------------------------------------------------------------------ #
    path("customers/me/", MyCustomerProfileView.as_view(), name="customer-me"),
]