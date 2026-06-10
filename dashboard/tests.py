from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from orders.models import Order

User = get_user_model()

class DashboardSummaryAPITests(APITestCase):
    def setUp(self):
        # Create users
        self.admin = User.objects.create_superuser(email="admin@example.com", password="password123")
        self.customer = User.objects.create_user(email="c1@example.com", password="password123")
        
        # Create orders at different stages
        # 1. Order Placed: WL Kurti (100 pcs, top wear)
        Order.objects.create(
            order_type="white_label",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=100,
            garment_type="Kurti",
            status="order_placed",
            assigned_to=self.admin
        )
        
        # 2. Advance Paid: PL Pant (250 pcs, bottom wear)
        Order.objects.create(
            order_type="private_label",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=250,
            garment_type="pant",
            status="advance_paid",
            assigned_to=self.admin
        )
        
        # 3. Order Confirmed: Fabric order (500 meters)
        Order.objects.create(
            order_type="fabrics",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=500,
            status="order_confirmed",
            assigned_to=self.admin
        )
        
        # 4. Delivered: WL Hoodie (50 pcs, top wear)
        Order.objects.create(
            order_type="white_label",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=50,
            garment_type="hoodie",
            status="delivered",
            assigned_to=self.admin
        )

    def test_state_wise_summary_stats(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("dashboard-summary")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify state_wise_stats in response
        self.assertIn("state_wise_stats", response.data)
        stats_list = response.data["state_wise_stats"]
        
        # We expect 4 active stages: order_placed, order_confirmed, advance_paid, delivered
        self.assertEqual(len(stats_list), 4)
        
        # Check correct logical sorting order:
        # Pipeline: order_placed -> order_confirmed -> advance_paid -> delivered
        self.assertEqual(stats_list[0]["state"], "order_placed")
        self.assertEqual(stats_list[0]["display_name"], "Order Placed")
        
        self.assertEqual(stats_list[1]["state"], "order_confirmed")
        self.assertEqual(stats_list[1]["display_name"], "Order Confirmed")
        
        self.assertEqual(stats_list[2]["state"], "advance_paid")
        self.assertEqual(stats_list[2]["display_name"], "Advance Paid")
        
        self.assertEqual(stats_list[3]["state"], "delivered")
        self.assertEqual(stats_list[3]["display_name"], "Delivered")
        
        # Convert list to dictionary for assertions
        stats_by_stage = {item["state"]: item for item in stats_list}
        
        # Order Placed assertions
        op = stats_by_stage["order_placed"]
        self.assertEqual(op["wl_orders"], 1)
        self.assertEqual(op["wl_pieces"], 100)
        self.assertEqual(op["pl_orders"], 0)
        self.assertEqual(op["pl_pieces"], 0)
        self.assertEqual(op["combined_orders"], 1)
        self.assertEqual(op["combined_pieces"], 100)
        self.assertEqual(op["fabrics_orders"], 0)
        self.assertEqual(op["fabrics_meters"], 0)
        
        # Order Confirmed assertions
        oc = stats_by_stage["order_confirmed"]
        self.assertEqual(oc["wl_orders"], 0)
        self.assertEqual(oc["wl_pieces"], 0)
        self.assertEqual(oc["pl_orders"], 0)
        self.assertEqual(oc["pl_pieces"], 0)
        self.assertEqual(oc["combined_orders"], 0)
        self.assertEqual(oc["combined_pieces"], 0)
        self.assertEqual(oc["fabrics_orders"], 1)
        self.assertEqual(oc["fabrics_meters"], 500)
        
        # Advance Paid assertions
        ap = stats_by_stage["advance_paid"]
        self.assertEqual(ap["wl_orders"], 0)
        self.assertEqual(ap["wl_pieces"], 0)
        self.assertEqual(ap["pl_orders"], 1)
        self.assertEqual(ap["pl_pieces"], 250)
        self.assertEqual(ap["combined_orders"], 1)
        self.assertEqual(ap["combined_pieces"], 250)
        self.assertEqual(ap["fabrics_orders"], 0)
        self.assertEqual(ap["fabrics_meters"], 0)
        
        # Delivered assertions
        dl = stats_by_stage["delivered"]
        self.assertEqual(dl["wl_orders"], 1)
        self.assertEqual(dl["wl_pieces"], 50)
        self.assertEqual(dl["pl_orders"], 0)
        self.assertEqual(dl["pl_pieces"], 0)
        self.assertEqual(dl["combined_orders"], 1)
        self.assertEqual(dl["combined_pieces"], 50)
        self.assertEqual(dl["fabrics_orders"], 0)
        self.assertEqual(dl["fabrics_meters"], 0)


class DashboardSummaryFilterTests(APITestCase):
    def setUp(self):
        # Create user roles / objects
        self.admin = User.objects.create_superuser(email="admin@example.com", password="password123")
        self.staff_a = User.objects.create_staff_user(email="staff_a@example.com", password="password123")
        self.staff_b = User.objects.create_staff_user(email="staff_b@example.com", password="password123")
        self.customer = User.objects.create_user(email="customer@example.com", password="password123")

        # Create orders
        # Order 1: Assigned to Staff A (White Label, order_placed, 100 qty)
        self.order_a = Order.objects.create(
            order_type="white_label",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=100,
            status="order_placed",
            assigned_to=self.staff_a
        )
        # Order 2: Assigned to Staff B (Private Label, advance_paid, 200 qty)
        self.order_b = Order.objects.create(
            order_type="private_label",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=200,
            status="advance_paid",
            assigned_to=self.staff_b
        )
        # Order 3: Unassigned (Fabrics, order_confirmed, 300 qty)
        self.order_c = Order.objects.create(
            order_type="fabrics",
            customer_user=self.customer,
            created_by_user=self.admin,
            total_quantity=300,
            status="order_confirmed"
        )

    def test_staff_a_only_sees_assigned_orders_in_pipeline(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("dashboard-summary")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("state_wise_stats", response.data)
        stats_list = response.data["state_wise_stats"]

        # Staff A should only see order_placed (from order_a)
        self.assertEqual(len(stats_list), 1)
        self.assertEqual(stats_list[0]["state"], "order_placed")
        self.assertEqual(stats_list[0]["wl_orders"], 1)
        self.assertEqual(stats_list[0]["wl_pieces"], 100)

    def test_staff_b_only_sees_assigned_orders_in_pipeline(self):
        self.client.force_authenticate(user=self.staff_b)
        url = reverse("dashboard-summary")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("state_wise_stats", response.data)
        stats_list = response.data["state_wise_stats"]

        # Staff B should only see advance_paid (from order_b)
        self.assertEqual(len(stats_list), 1)
        self.assertEqual(stats_list[0]["state"], "advance_paid")
        self.assertEqual(stats_list[0]["pl_orders"], 1)
        self.assertEqual(stats_list[0]["pl_pieces"], 200)

    def test_admin_only_sees_assigned_orders_in_pipeline(self):
        # Assign order_c to admin
        self.order_c.assigned_to = self.admin
        self.order_c.save()

        self.client.force_authenticate(user=self.admin)
        url = reverse("dashboard-summary")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("state_wise_stats", response.data)
        stats_list = response.data["state_wise_stats"]

        # Admin should only see order_c (Fabrics, order_confirmed, 300 qty)
        self.assertEqual(len(stats_list), 1)
        self.assertEqual(stats_list[0]["state"], "order_confirmed")
        self.assertEqual(stats_list[0]["fabrics_orders"], 1)
        self.assertEqual(stats_list[0]["fabrics_meters"], 300)


