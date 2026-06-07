from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from orders.models import Order

User = get_user_model()

class OrderWorkflowTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="customer@example.com", password="password123")
        self.admin = User.objects.create_superuser(email="admin@example.com", password="password123")

    def test_order_confirmed_constraints(self):
        # Create White Label order in placed state
        order = Order.objects.create(
            order_type="white_label",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=100,
            status="order_placed"
        )
        
        # Changing status to order_confirmed without total_amount or advance_amount should fail model validation
        order.status = "order_confirmed"
        with self.assertRaises(ValidationError) as ctx:
            order.clean()
        
        self.assertIn("total_amount", ctx.exception.message_dict)
        self.assertIn("advance_amount", ctx.exception.message_dict)
            
        # Try with only total_amount
        order.total_amount = 5000.00
        with self.assertRaises(ValidationError) as ctx:
            order.clean()
        self.assertIn("advance_amount", ctx.exception.message_dict)
        self.assertNotIn("total_amount", ctx.exception.message_dict)
            
        # Try with both filled but <= 0
        order.advance_amount = -100.00
        with self.assertRaises(ValidationError):
            order.clean()

        # Both positive should succeed
        order.advance_amount = 2500.00
        order.clean()
        order.save()
        self.assertEqual(order.status, "order_confirmed")

    def test_po_summary_availability(self):
        order = Order.objects.create(
            order_type="white_label",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=100,
            status="order_placed"
        )
        
        # Initially not available
        self.assertFalse(order.is_po_summary_available)
        
        # Set to order_confirmed with correct amounts
        order.status = "order_confirmed"
        order.total_amount = 5000.00
        order.advance_amount = 2500.00
        order.save()
        self.assertTrue(order.is_po_summary_available)
        
        # Test Fabric order with swatch
        fabric_order_swatch = Order.objects.create(
            order_type="fabrics",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=100,
            swatch_required=True,
            status="order_placed"
        )
        self.assertFalse(fabric_order_swatch.is_po_summary_available)
        
        fabric_order_swatch.status = "swatch_approved"
        fabric_order_swatch.save()
        self.assertTrue(fabric_order_swatch.is_po_summary_available)

    def test_size_breakdown_editable(self):
        order = Order.objects.create(
            order_type="white_label",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=100,
            status="order_placed"
        )
        
        self.assertTrue(order.is_size_breakdown_editable)
        
        # Move to confirmed
        order.status = "order_confirmed"
        order.total_amount = 5000.00
        order.advance_amount = 2500.00
        order.save()
        self.assertFalse(order.is_size_breakdown_editable)


class OrderAPITests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="customer@example.com", password="password123")
        self.admin = User.objects.create_superuser(email="admin@example.com", password="password123")
        
        # Create an order
        self.order = Order.objects.create(
            order_type="white_label",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=100,
            status="order_placed",
            size_breakdown=[{"size": "M", "quantity": 100}]
        )

    def test_api_status_update_validation(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("order-status-update", kwargs={"id": self.order.id})
        
        # Update to order_confirmed without total_amount or advance_amount should fail API validation
        response = self.client.patch(url, {"status": "order_confirmed"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("total_amount", response.data)
        self.assertIn("advance_amount", response.data)
        
        # Succeeded with both filled
        response = self.client.patch(url, {
            "status": "order_confirmed",
            "total_amount": 5000.00,
            "advance_amount": 2500.00
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check database
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "order_confirmed")
        self.assertEqual(self.order.total_amount, 5000.00)
        self.assertEqual(self.order.advance_amount, 2500.00)

    def test_api_size_breakdown_edit_lock(self):
        # When status is order_placed, client should be able to update size breakdown
        self.client.force_authenticate(user=self.admin)
        url = reverse("order-detail", kwargs={"id": self.order.id})
        
        new_breakdown = [{"size": "L", "quantity": 100}]
        response = self.client.patch(url, {"size_breakdown": new_breakdown}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        
        # Confirm it saved
        self.order.refresh_from_db()
        self.assertEqual(self.order.size_breakdown, new_breakdown)
        
        # Confirm order and verify that editing size breakdown is rejected
        self.order.status = "order_confirmed"
        self.order.total_amount = 6000.00
        self.order.advance_amount = 3000.00
        self.order.save()
        
        response = self.client.patch(url, {"size_breakdown": [{"size": "XL", "quantity": 100}]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_api_po_summary_download_restriction(self):
        url = reverse("order-po-summary", kwargs={"id": self.order.id})
        
        # Attempt download before confirmation -> Rejected
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        
        # Confirm order
        self.order.status = "order_confirmed"
        self.order.total_amount = 5000.00
        self.order.advance_amount = 2500.00
        self.order.save()
        
        # Attempt download after confirmation -> Approved/Generated
        # In test mode, profile setup might fail, let's create a Customer profile for the customer
        from accounts.models import Customer
        Customer.objects.create(
            user=self.customer,
            brand_name="Brand X",
            contact_name="Contact X",
            phone="1234567890"
        )
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers["Content-Type"], "application/pdf")
