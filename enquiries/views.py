from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import Enquiry
from .serializers import (
    EnquiryCreateSerializer,
    EnquiryResponseSerializer,
    EnquiryListSerializer,
    EnquiryDetailSerializer,
    EnquiryUpdateSerializer,
)
from accounts.permissions import IsAdmin, IsAdminOrStaff


# ── FILTER ─────────────────────────────────────────────────────────────

class EnquiryFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to   = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model  = Enquiry
        fields = ['order_type', 'status', 'is_viewed', 'source_page', 'assigned_to_user']


# ── PUBLIC: CREATE ENQUIRY ─────────────────────────────────────────────

class EnquiryCreateView(APIView):
    """
    POST /api/enquiries/
    Public — no login required.
    Accepts multipart/form-data for image uploads.
    """
    permission_classes = [AllowAny]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        # Pull images separately from request.FILES
        data       = request.data.copy()
        image_list = request.FILES.getlist('images')

        serializer = EnquiryCreateSerializer(
            data={**data, 'images': image_list},
            context={'request': request},
        )
        if serializer.is_valid():
            enquiry  = serializer.save()
            response = EnquiryResponseSerializer(enquiry, context={'request': request})
            return Response(
                {"message": "Enquiry submitted successfully.", "data": response.data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── ADMIN: LIST ALL ENQUIRIES ──────────────────────────────────────────

class EnquiryListView(generics.ListAPIView):
    """
    GET /api/enquiries/admin/
    Admin & Staff only — list all enquiries with filters.

    Filters:
      ?order_type=      private_label | white_label | fabrics | others
      ?status=          new | contacted | waiting_response | prospect | accepted | rejected | closed
      ?is_viewed=       true | false
      ?source_page=     general | private_label_page | white_label_page | fabrics_page
      ?assigned_to_user= <user_uuid>
      ?date_from=       2026-01-01
      ?date_to=         2026-03-15
      ?search=          name, email, phone, brand, enquiry number
      ?ordering=        created_at | -created_at | status | order_type
    """
    serializer_class   = EnquiryListSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class    = EnquiryFilter
    search_fields      = ['enquiry_number', 'full_name', 'email', 'phone', 'brand_name']
    ordering_fields    = ['created_at', 'status', 'order_type']
    ordering           = ['-created_at']

    def get_queryset(self):
        return Enquiry.objects.select_related(
            'assigned_to_user', 'wl_prototype', 'fabric', 'customer'
        ).all()


# ── ADMIN: GET / UPDATE SINGLE ENQUIRY ────────────────────────────────

class EnquiryDetailView(APIView):
    """
    GET   /api/enquiries/admin/<id>/  — get full detail, auto-marks as viewed
    PATCH /api/enquiries/admin/<id>/  — update status, assignee, notes
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get_object(self, id):
        try:
            return Enquiry.objects.select_related(
                'assigned_to_user', 'wl_prototype', 'fabric', 'customer'
            ).prefetch_related('images').get(id=id)
        except Enquiry.DoesNotExist:
            return None

    def get(self, request, id):
        enquiry = self.get_object(id)
        if not enquiry:
            return Response({"error": "Enquiry not found."}, status=status.HTTP_404_NOT_FOUND)

        # Auto-mark as viewed
        if not enquiry.is_viewed:
            enquiry.is_viewed = True
            enquiry.viewed_at = timezone.now()
            enquiry.save(update_fields=['is_viewed', 'viewed_at'])

        serializer = EnquiryDetailSerializer(enquiry, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, id):
        enquiry = self.get_object(id)
        if not enquiry:
            return Response({"error": "Enquiry not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EnquiryUpdateSerializer(enquiry, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # Return full detail after update
            detail = EnquiryDetailSerializer(enquiry, context={'request': request})
            return Response(detail.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── ADMIN: UNREAD COUNT ────────────────────────────────────────────────

class EnquiryUnreadCountView(APIView):
    """
    GET /api/enquiries/admin/unread-count/
    Returns count of unread enquiries grouped by order_type.
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        unread = Enquiry.objects.filter(is_viewed=False)
        return Response({
            "total":         unread.count(),
            "private_label": unread.filter(order_type='private_label').count(),
            "white_label":   unread.filter(order_type='white_label').count(),
            "fabrics":       unread.filter(order_type='fabrics').count(),
            "others":        unread.filter(order_type='others').count(),
        })