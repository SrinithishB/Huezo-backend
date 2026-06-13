# orders/filters.py

from django_filters import rest_framework as django_filters
from .models import Order

class OrderFilter(django_filters.FilterSet):
    date_from     = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to       = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")
    assigned_to   = django_filters.UUIDFilter(field_name="assigned_to__id")
    unassigned    = django_filters.BooleanFilter(field_name="assigned_to", lookup_expr="isnull")
    customer_user = django_filters.UUIDFilter(field_name="customer_user__id")
    status_in     = django_filters.CharFilter(method="filter_status_in")
    order_type_in = django_filters.CharFilter(method="filter_order_type_in")

    def filter_status_in(self, queryset, name, value):
        statuses = [s.strip() for s in value.split(",") if s.strip()]
        if statuses:
            return queryset.filter(status__in=statuses)
        return queryset

    def filter_order_type_in(self, queryset, name, value):
        types = [t.strip() for t in value.split(",") if t.strip()]
        if types:
            return queryset.filter(order_type__in=types)
        return queryset

    class Meta:
        model  = Order
        fields = ["order_type", "status", "fabric_type", "for_category", "assigned_to", "customer_user"]
