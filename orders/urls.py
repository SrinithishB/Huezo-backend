from django.urls import path
from .views import (
    OrderCreateView,
    OrderListView,
    OrderDetailView,
    OrderStatusUpdateView,
    OrderNotesView,
)

urlpatterns = [
    # ── Create orders ──────────────────────────────────────────────── #
    path("orders/wl/",      OrderCreateView.as_view(), {"order_type": "wl"},      name="order-create-wl"),
    path("orders/pl/",      OrderCreateView.as_view(), {"order_type": "pl"},      name="order-create-pl"),
    path("orders/fabrics/", OrderCreateView.as_view(), {"order_type": "fabrics"}, name="order-create-fabrics"),

    # ── List & Detail ──────────────────────────────────────────────── #
    path("orders/",                  OrderListView.as_view(),         name="order-list"),
    path("orders/<uuid:id>/",        OrderDetailView.as_view(),       name="order-detail"),

    # ── Admin: update stage ────────────────────────────────────────── #
    path("orders/<uuid:id>/status/", OrderStatusUpdateView.as_view(), name="order-status-update"),

    # ── Notes (admin + customer) ───────────────────────────────────── #
    path("orders/<uuid:id>/notes/",  OrderNotesView.as_view(),        name="order-notes"),
]