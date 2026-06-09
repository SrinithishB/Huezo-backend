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
        # Priority 2: Non-prebooks:
        #   - WL-01
        # Priority 3: Ended prebooks:
        #   - WL-02 (-3 days from now)
        
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
                When(is_prebooking=True, prebooking_close_date__lt=today, then=Value(3)),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by("sort_priority", "prebooking_close_date", "-created_at")
        
        details = []
        for x in annotated:
            details.append(f"{x.prototype_code}: priority={x.sort_priority}, close={x.prebooking_close_date}, is_prebooking={x.is_prebooking}")
        
        expected_codes = ["WL-03", "WL-04", "WL-01", "WL-02"]
        self.assertEqual(codes, expected_codes, "\n".join(details))


from django.core.files.uploadedfile import SimpleUploadedFile
from catalogue.models import WLPrototypeImage

class WLPrototypeThumbnailSyncTests(TestCase):
    def setUp(self):
        self.prototype = WLPrototype.objects.create(
            prototype_code="WL-TEST-SYNC",
            for_gender="women",
            moq=15,
            is_active=True
        )
        self.test_image_1 = SimpleUploadedFile("test1.jpg", b"file_content_1", content_type="image/jpeg")
        self.test_image_2 = SimpleUploadedFile("test2.jpg", b"file_content_2", content_type="image/jpeg")

    def test_thumbnail_synchronization(self):
        # 1. Add image without is_thumbnail
        img1 = WLPrototypeImage.objects.create(
            prototype=self.prototype,
            image=self.test_image_1,
            is_thumbnail=False
        )
        self.prototype.refresh_from_db()
        self.assertFalse(bool(self.prototype.thumbnail))

        # 2. Toggle is_thumbnail on img1
        img1.is_thumbnail = True
        img1.save()
        self.prototype.refresh_from_db()
        self.assertTrue("test1" in self.prototype.thumbnail.name)

        # 3. Create second image with is_thumbnail=True
        img2 = WLPrototypeImage.objects.create(
            prototype=self.prototype,
            image=self.test_image_2,
            is_thumbnail=True
        )
        
        # Verify img1 is no longer thumbnail, and parent thumbnail points to img2
        img1.refresh_from_db()
        self.assertFalse(img1.is_thumbnail)
        self.prototype.refresh_from_db()
        self.assertTrue("test2" in self.prototype.thumbnail.name)

        # 4. Toggle is_thumbnail off on img2
        img2.is_thumbnail = False
        img2.save()
        self.prototype.refresh_from_db()
        # Should clear the prototype thumbnail since no other image is marked as thumbnail
        self.assertFalse(bool(self.prototype.thumbnail))

        # 5. Set img1 back to thumbnail
        img1.is_thumbnail = True
        img1.save()
        self.prototype.refresh_from_db()
        self.assertTrue("test1" in self.prototype.thumbnail.name)

        # 6. Delete img1
        img1.delete()
        self.prototype.refresh_from_db()
        self.assertFalse(bool(self.prototype.thumbnail))

    def test_formset_validation_prevents_multiple_thumbnails(self):
        from django.forms import inlineformset_factory
        from catalogue.admin import WLPrototypeImageFormSet

        # Create inline formset factory
        ImageFormSet = inlineformset_factory(
            WLPrototype,
            WLPrototypeImage,
            formset=WLPrototypeImageFormSet,
            fields=["image", "is_thumbnail", "sort_order"],
            extra=2
        )

        # Formset data with two images checked as thumbnail
        data = {
            "images-TOTAL_FORMS": "2",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "1000",
            "images-0-image": SimpleUploadedFile("test1.jpg", b"content1", content_type="image/jpeg"),
            "images-0-is_thumbnail": "on",
            "images-0-sort_order": "0",
            "images-1-image": SimpleUploadedFile("test2.jpg", b"content2", content_type="image/jpeg"),
            "images-1-is_thumbnail": "on",
            "images-1-sort_order": "1",
        }

        formset = ImageFormSet(data=data, instance=self.prototype, files=data)
        # Should be invalid because both are checked as thumbnail
        self.assertFalse(formset.is_valid())
        self.assertIn("You can only select one image as the thumbnail.", formset.non_form_errors())


from django.db import IntegrityError
from catalogue.models import FabricsCatalogue

class FabricsCatalogueSKUTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="customer-fabric@example.com", password="password123")
        self.client.force_authenticate(user=self.customer)

    def test_fabric_sku_uniqueness(self):
        # 1. Create a fabric with a unique SKU
        fabric1 = FabricsCatalogue.objects.create(
            fabric_name="Cotton Linen",
            fabric_type="regular",
            sku="FAB-COTTON-01"
        )
        self.assertEqual(fabric1.sku, "FAB-COTTON-01")

        # 2. Try to create another fabric with the exact same SKU
        with self.assertRaises(IntegrityError):
            FabricsCatalogue.objects.create(
                fabric_name="Linen Blend",
                fabric_type="regular",
                sku="FAB-COTTON-01"
            )

    def test_fabric_sku_in_api_responses(self):
        # Create fabric
        fabric = FabricsCatalogue.objects.create(
            fabric_name="Premium Silk",
            fabric_type="new",
            sku="FAB-SILK-99",
            is_active=True
        )

        # Query fabric list API
        url_list = reverse("fabrics-list")
        response = self.client.get(url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        fabric_data = next(item for item in results if item["id"] == str(fabric.id))
        self.assertEqual(fabric_data["sku"], "FAB-SILK-99")

        # Query fabric detail API
        url_detail = reverse("fabrics-detail", kwargs={"id": fabric.id})
        response = self.client.get(url_detail)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sku"], "FAB-SILK-99")

    def test_fabric_formset_validation_prevents_multiple_thumbnails(self):
        from django.forms import inlineformset_factory
        from catalogue.admin import FabricsCatalogueImageFormSet
        from catalogue.models import FabricsCatalogueImage

        # Create inline formset factory
        ImageFormSet = inlineformset_factory(
            FabricsCatalogue,
            FabricsCatalogueImage,
            formset=FabricsCatalogueImageFormSet,
            fields=["image", "is_thumbnail", "sort_order"],
            extra=2
        )

        fabric = FabricsCatalogue.objects.create(
            fabric_name="Premium Wool",
            fabric_type="new",
            sku="FAB-WOOL-01"
        )

        # Formset data with two images checked as thumbnail
        data = {
            "images-TOTAL_FORMS": "2",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "1000",
            "images-0-image": SimpleUploadedFile("test1.jpg", b"content1", content_type="image/jpeg"),
            "images-0-is_thumbnail": "on",
            "images-0-sort_order": "0",
            "images-1-image": SimpleUploadedFile("test2.jpg", b"content2", content_type="image/jpeg"),
            "images-1-is_thumbnail": "on",
            "images-1-sort_order": "1",
        }

        formset = ImageFormSet(data=data, instance=fabric, files=data)
        # Should be invalid because both are checked as thumbnail
        self.assertFalse(formset.is_valid())
        self.assertIn("You can only select one image as the thumbnail.", formset.non_form_errors())
