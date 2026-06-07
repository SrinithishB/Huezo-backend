from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from catalogue.models import WLPrototype

User = get_user_model()

class CatalogueSortingTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="customer@example.com", password="password123")
        self.client.force_authenticate(user=self.customer)
        
        today = timezone.now().date()
        
        # 1. Non prebook
        self.non_prebook = WLPrototype.objects.create(
            prototype_code="WL-01",
            for_gender="women",
            moq=15,
            is_prebooking=False,
            is_active=True
        )
        
        # 2. Ended prebook
        self.ended_prebook = WLPrototype.objects.create(
            prototype_code="WL-02",
            for_gender="women",
            moq=15,
            is_prebooking=True,
            prebooking_close_date=today - timedelta(days=3),
            is_active=True
        )
        
        # 3. Active prebook closing soon
        self.active_soon = WLPrototype.objects.create(
            prototype_code="WL-03",
            for_gender="women",
            moq=15,
            is_prebooking=True,
            prebooking_close_date=today + timedelta(days=2),
            is_active=True
        )
        
        # 4. Active prebook closing later
        self.active_later = WLPrototype.objects.create(
            prototype_code="WL-04",
            for_gender="women",
            moq=15,
            is_prebooking=True,
            prebooking_close_date=today + timedelta(days=10),
            is_active=True
        )

    def test_catalogue_list_sorting_order(self):
        url = reverse("catalogue-wl-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # The expected order is:
        # Priority 1: Active prebooks, sorted by prebooking_close_date ASC:
        #   - WL-03 (2 days from now)
        #   - WL-04 (10 days from now)
        # Priority 2: Ended prebooks:
        #   - WL-02 (-3 days from now)
        # Priority 3: Non-prebooks:
        #   - WL-01
        
        results = response.data.get("results", response.data)
        codes = [item["prototype_code"] for item in results]
        
        # Let's get the DB values for debugging
        db_qs = WLPrototype.objects.filter(is_active=True)
        from django.db.models import Case, When, Value, IntegerField
        from django.utils import timezone
        today = timezone.now().date()
        annotated = db_qs.annotate(
            sort_priority=Case(
                When(is_prebooking=True, prebooking_close_date__gte=today, then=Value(1)),
                When(is_prebooking=True, prebooking_close_date__lt=today, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        ).order_by("sort_priority", "prebooking_close_date", "-created_at")
        
        details = []
        for x in annotated:
            details.append(f"{x.prototype_code}: priority={x.sort_priority}, close={x.prebooking_close_date}, is_prebooking={x.is_prebooking}")
        
        expected_codes = ["WL-03", "WL-04", "WL-02", "WL-01"]
        self.assertEqual(codes, expected_codes, "\n".join(details))
