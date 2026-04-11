# lib/features/orders/urls.py
# Replace your existing orders/urls.py with this

from django.urls import path
from .views import (
    OrderCreateView,
    StaffOrderCreateView,
    OrderListView,
    OrderDetailView,
    OrderStatusUpdateView,
    OrderNotesView,
    OrderInvoiceView,
    OrderAssignView,
)

urlpatterns = [
    # ── Create orders (customer) ───────────────────────────────────── #
    path("orders/wl/",      OrderCreateView.as_view(), {"order_type": "wl"},      name="order-create-wl"),
    path("orders/pl/",      OrderCreateView.as_view(), {"order_type": "pl"},      name="order-create-pl"),
    path("orders/fabrics/", OrderCreateView.as_view(), {"order_type": "fabrics"}, name="order-create-fabrics"),

    # ── Create orders (staff on behalf of customer) ────────────────── #
    path("orders/staff/wl/",      StaffOrderCreateView.as_view(), {"order_type": "wl"},      name="staff-order-create-wl"),
    path("orders/staff/fabrics/", StaffOrderCreateView.as_view(), {"order_type": "fabrics"}, name="staff-order-create-fabrics"),

    # ── List & Detail ──────────────────────────────────────────────── #
    path("orders/",                  OrderListView.as_view(),         name="order-list"),
    path("orders/<uuid:id>/",        OrderDetailView.as_view(),       name="order-detail"),

    # ── Invoice (customer + admin) ─────────────────────────────────── #
    path("orders/<uuid:id>/invoice/", OrderInvoiceView.as_view(),     name="order-invoice"),

    # ── Admin: update stage ────────────────────────────────────────── #
    path("orders/<uuid:id>/status/", OrderStatusUpdateView.as_view(), name="order-status-update"),

    # ── Notes (admin + customer) ───────────────────────────────────── #
    path("orders/<uuid:id>/notes/",  OrderNotesView.as_view(),        name="order-notes"),

    # ── Admin: assign staff ────────────────────────────────────────── #
    path("orders/<uuid:id>/assign/", OrderAssignView.as_view(),       name="order-assign"),
]