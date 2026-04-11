from django.urls import path
from .views import (
    OrderPaymentCreateView,
    PaymentWebhookView,
    PaymentStatusView,
    PaymentTransactionListView,
    PaymentVerifyView,
)

urlpatterns = [
    # Webhook — single endpoint for ALL payment types
    path("payments/webhook/",                        PaymentWebhookView.as_view(),          name="payment-webhook"),

    # Order payments
    path("payments/orders/<uuid:order_id>/create/",  OrderPaymentCreateView.as_view(),      name="order-payment-create"),
    path("payments/orders/<uuid:order_id>/status/",  PaymentStatusView.as_view(),            name="order-payment-status"),

    # Admin
    path("payments/transactions/",                   PaymentTransactionListView.as_view(),  name="payment-transactions"),
    path("payments/orders/<uuid:order_id>/verify/", PaymentVerifyView.as_view(), name="order-payment-verify"),
]