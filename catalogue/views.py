from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import WLPrototype
from .serializers import WLPrototypeListSerializer, WLPrototypeDetailSerializer


# CUSTOM FILTER
class WLPrototypeFilter(django_filters.FilterSet):
    """
    Allows filtering by:
      - for_gender        exact match         ?for_gender=women
      - garment_type      case-insensitive    ?garment_type=kurti
      - collection_name   case-insensitive    ?collection_name=diwali
      - is_prebooking     boolean             ?is_prebooking=true
      - moq_min / moq_max range              ?moq_min=10&moq_max=50
    """
    garment_type    = django_filters.CharFilter(lookup_expr="icontains")
    collection_name = django_filters.CharFilter(lookup_expr="icontains")
    moq_min         = django_filters.NumberFilter(field_name="moq", lookup_expr="gte")
    moq_max         = django_filters.NumberFilter(field_name="moq", lookup_expr="lte")

    class Meta:
        model  = WLPrototype
        fields = ["for_gender", "garment_type", "collection_name", "is_prebooking"]


# VIEWS
class CatalogueListView(generics.ListAPIView):
    """
    GET /api/catalogue/
    Returns a paginated list of active prototypes.
    Only authenticated users (customers, staff, admin) can access.

    Query Parameters:
      Search:
        ?search=          searches prototype_code, garment_type, collection_name

      Filters:
        ?for_gender=      women | men | kids
        ?garment_type=    kurti (partial match)
        ?collection_name= diwali (partial match)
        ?is_prebooking=   true | false
        ?moq_min=         minimum MOQ
        ?moq_max=         maximum MOQ

      Ordering:
        ?ordering=        created_at | -created_at | moq | prototype_code

      Pagination:
        ?page=            page number (default page size = 20)
    """
    serializer_class   = WLPrototypeListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class    = WLPrototypeFilter
    search_fields      = ["prototype_code", "garment_type", "collection_name"]
    ordering_fields    = ["created_at", "moq", "prototype_code"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        # Only return active prototypes to customers
        return WLPrototype.objects.filter(
            is_active=True
        ).prefetch_related("images")


class CatalogueDetailView(generics.RetrieveAPIView):
    """
    GET /api/catalogue/<id>/
    Returns full detail of a single prototype including all gallery images.
    Only active prototypes are visible to customers.
    """
    serializer_class   = WLPrototypeDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field       = "id"

    def get_queryset(self):
        return WLPrototype.objects.filter(is_active=True).prefetch_related("images","created_by_admin",)