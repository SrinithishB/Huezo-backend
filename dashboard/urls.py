from django.urls import path
from .views import (
    ExportEnquiriesView,
    ExportOrdersView,
    DashboardSummaryView,
)

urlpatterns = [
    path("dashboard/summary/",           DashboardSummaryView.as_view(),  name="dashboard-summary"),
    path("dashboard/export/enquiries/",  ExportEnquiriesView.as_view(),   name="export-enquiries"),
    path("dashboard/export/orders/",     ExportOrdersView.as_view(),      name="export-orders"),
]