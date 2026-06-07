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
    OrderCancelView,
    OrderPOSummaryView,
)

urlpatterns = [
    # ── Create orders (customer) ───────────────────────────────────── #
    path("orders/wl/",      OrderCreateView.as_view(), {"order_type": "wl"},      name="order-create-wl"),
    path("orders/pl/",      OrderCreateView.as_view(), {"order_type": "pl"},      name="order-create-pl"),
    path("orders/fabrics/", OrderCreateView.as_view(), {"order_type": "fabrics"}, name="order-create-fabrics"),

    # ── Create orders (staff on behalf of customer) ────────────────── #
    path("orders/staff/wl/",      StaffOrderCreateView.as_view(), {"order_type": "wl"},      name="staff-order-create-wl"),
    path("orders/staff/pl/",      StaffOrderCreateView.as_view(), {"order_type": "pl"},      name="staff-order-create-pl"),
    path("orders/staff/fabrics/", StaffOrderCreateView.as_view(), {"order_type": "fabrics"}, name="staff-order-create-fabrics"),

    # ── List & Detail ──────────────────────────────────────────────── #
    path("orders/",                  OrderListView.as_view(),         name="order-list"),
    path("orders/<uuid:id>/",        OrderDetailView.as_view(),       name="order-detail"),

    # ── Invoice (customer + admin) ─────────────────────────────────── #
    path("orders/<uuid:id>/invoice/", OrderInvoiceView.as_view(),     name="order-invoice"),

    # ── PO Summary (customer + admin) ───────────────────────────────── #
    path("orders/<uuid:id>/po-summary/", OrderPOSummaryView.as_view(), name="order-po-summary"),

    # ── Admin: update stage ────────────────────────────────────────── #
    path("orders/<uuid:id>/status/", OrderStatusUpdateView.as_view(), name="order-status-update"),

    # ── Notes (admin + customer) ───────────────────────────────────── #
    path("orders/<uuid:id>/notes/",  OrderNotesView.as_view(),        name="order-notes"),

    # ── Admin: assign staff ────────────────────────────────────────── #
    path("orders/<uuid:id>/assign/", OrderAssignView.as_view(),       name="order-assign"),

    # ── Cancel Order ────────────────────────────────────────────────── #
    path("orders/<uuid:id>/cancel/", OrderCancelView.as_view(),       name="order-cancel"),
]