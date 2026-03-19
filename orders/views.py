from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import Order, OrderStageHistory
from .serializers import (
    WLOrderCreateSerializer,
    PLOrderCreateSerializer,
    FabricsOrderCreateSerializer,
    OrderListSerializer,
    OrderDetailSerializer,
    OrderStatusUpdateSerializer,
)
from accounts.permissions import IsAdminOrStaff


# ── FILTER ─────────────────────────────────────────────────────────────

class OrderFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to   = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model  = Order
        fields = ["order_type", "status", "fabric_type", "for_category"]


# ── CREATE ORDER ───────────────────────────────────────────────────────

class OrderCreateView(APIView):
    """
    POST /api/orders/wl/       — White Label order
    POST /api/orders/pl/       — Private Label order
    POST /api/orders/fabrics/  — Fabrics order

    Customer is logged in — personal details auto-filled from session.
    Accepts multipart/form-data for image uploads.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    # Map order type to serializer
    SERIALIZER_MAP = {
        "wl":      WLOrderCreateSerializer,
        "pl":      PLOrderCreateSerializer,
        "fabrics": FabricsOrderCreateSerializer,
    }

    def post(self, request, order_type):
        serializer_class = self.SERIALIZER_MAP.get(order_type)
        if not serializer_class:
            return Response(
                {"error": "Invalid order type. Use wl, pl, or fabrics."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        images_data = request.FILES.getlist("images")
        serializer  = serializer_class(
            data    = {**request.data, "images": images_data},
            context = {"request": request},
        )
        if serializer.is_valid():
            order    = serializer.save()
            response = OrderDetailSerializer(order, context={"request": request})
            return Response(
                {"message": "Order placed successfully.", "data": response.data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── LIST ORDERS ────────────────────────────────────────────────────────

class OrderListView(generics.ListAPIView):
    """
    GET /api/orders/
    - Admin/Staff: all orders
    - Customer: own orders only

    Filters:
      ?order_type=   private_label | white_label | fabrics
      ?status=       order_placed | cutting | ...
      ?date_from=    2026-01-01
      ?date_to=      2026-03-15
      ?search=       order number, customer email
      ?ordering=     created_at | -created_at | status
    """
    serializer_class   = OrderListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class    = OrderFilter
    search_fields      = ["order_number", "customer_user__email", "style_name"]
    ordering_fields    = ["created_at", "status", "order_type"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs   = Order.objects.select_related(
            "customer_user", "white_label_catalogue", "fabric_catalogue",
        )
        if user.role == "customer":
            return qs.filter(customer_user=user)
        return qs.all()


# ── ORDER DETAIL ───────────────────────────────────────────────────────

class OrderDetailView(APIView):
    """
    GET /api/orders/<id>/
    Customer sees only their own. Admin/Staff sees all.
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, id, user):
        try:
            qs = Order.objects.select_related(
                "customer_user", "created_by_user", "enquiry",
                "white_label_catalogue", "fabric_catalogue",
            ).prefetch_related("images", "stage_history__changed_by")

            if user.role == "customer":
                return qs.get(id=id, customer_user=user)
            return qs.get(id=id)
        except Order.DoesNotExist:
            return None

    def get(self, request, id):
        order = self.get_object(id, request.user)
        if not order:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrderDetailSerializer(order, context={"request": request})
        return Response(serializer.data)


# ── UPDATE ORDER STATUS (Admin only) ──────────────────────────────────

class OrderStatusUpdateView(APIView):
    """
    PATCH /api/orders/<id>/status/
    Admin only — update stage and add to timeline.

    Input: { "status": "cutting", "notes": "optional note" }
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def patch(self, request, id):
        try:
            order = Order.objects.get(id=id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderStatusUpdateSerializer(
            data    = request.data,
            context = {"order": order},
        )
        if serializer.is_valid():
            new_status = serializer.validated_data["status"]
            notes      = serializer.validated_data.get("notes", "")

            order.status = new_status
            order.save(update_fields=["status", "updated_at"])

            OrderStageHistory.objects.create(
                order      = order,
                stage      = new_status,
                changed_by = request.user,
                notes      = notes,
            )

            detail = OrderDetailSerializer(order, context={"request": request})
            return Response(detail.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── ORDER NOTES ────────────────────────────────────────────────────────

class OrderNotesView(APIView):
    """
    GET  /api/orders/<uuid>/notes/  — list all notes for an order
    POST /api/orders/<uuid>/notes/  — add a note to an order

    - Admin/Staff can add notes on any order
    - Customer can add notes on their own orders only
    - All parties can view notes on their accessible orders
    """
    permission_classes = [IsAuthenticated]

    def get_order(self, id, user):
        from .models import Order
        try:
            if user.role == "customer":
                return Order.objects.get(id=id, customer_user=user)
            return Order.objects.get(id=id)
        except Order.DoesNotExist:
            return None

    def get(self, request, id):
        from .models import OrderNote
        from .serializers import OrderNoteSerializer

        order = self.get_order(id, request.user)
        if not order:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        notes = OrderNote.objects.filter(order=order).select_related("added_by")
        serializer = OrderNoteSerializer(notes, many=True)
        return Response(serializer.data)

    def post(self, request, id):
        from .models import OrderNote
        from .serializers import OrderNoteCreateSerializer, OrderNoteSerializer

        order = self.get_order(id, request.user)
        if not order:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderNoteCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        note = OrderNote.objects.create(
            order    = order,
            note     = serializer.validated_data["note"],
            added_by = request.user,
        )
        return Response(
            OrderNoteSerializer(note).data,
            status=status.HTTP_201_CREATED,
        )