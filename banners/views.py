from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Banner
from .serializers import BannerSerializer


class BannerListView(generics.ListAPIView):
    """
    GET /api/banners/
    Returns all active banners ordered by sort_order.
    """
    serializer_class   = BannerSerializer
    permission_classes = [IsAuthenticated]
    pagination_class   = None  # Return all banners at once (no pagination)

    def get_queryset(self):
        return Banner.objects.filter(is_active=True)
