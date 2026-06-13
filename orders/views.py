# orders/views.py

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse

from .models import Order, OrderStageHistory
from .serializers import (
    WLOrderCreateSerializer,
    PLOrderCreateSerializer,
    FabricsOrderCreateSerializer,
    StaffWLOrderCreateSerializer,
    StaffFabricsOrderCreateSerializer,
    StaffPLOrderCreateSerializer,
    OrderListSerializer,
    OrderDetailSerializer,
    OrderStatusUpdateSerializer,
    OrderAssignSerializer,
)
from accounts.permissions import IsAdminOrStaff
from .filters import OrderFilter
from .pdf import generate_invoice_pdf, generate_po_summary_pdf


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

        if hasattr(request.data, "dict"):
            data = request.data.dict()
        else:
            data = dict(request.data)
        images_data = request.FILES.getlist("images")
        data["images"] = images_data

        serializer = serializer_class(
            data    = data,
            context = {"request": request},
        )
        if serializer.is_valid():
            order    = serializer.save()
            
            # Send notification to superusers/admins
            try:
                from notifications.service import notify_superusers
                notify_superusers(
                    "🛒 New Order Placed",
                    f"Order {order.order_number} has been placed successfully by {order.customer_user.email}.",
                    {
                        "type": "new_order",
                        "order_id": str(order.id),
                        "order_number": order.order_number,
                    }
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Order notification failed: {e}")
                
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
            "customer_user", "customer_user__customer_profile", "white_label_catalogue", "fabric_catalogue", "assigned_to",
        ).prefetch_related(
            "fabric_catalogue__images", "images",
        )
        if user.role in ("admin", "staff"):
            return qs.all()
        elif user.role == "customer":
            return qs.filter(customer_user=user)
        return qs.none()


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
                "customer_user", "customer_user__customer_profile", "created_by_user", "enquiry",
                "white_label_catalogue", "fabric_catalogue",
                "pl_fabric_1", "pl_fabric_2", "pl_fabric_3",
            ).prefetch_related(
                "images",
                "stage_history__changed_by",
                "white_label_catalogue__images",
                "fabric_catalogue__images",
                "pl_fabric_1__images",
                "pl_fabric_2__images",
                "pl_fabric_3__images",
            )

            if user.role in ("admin", "staff"):
                return qs.get(id=id)
            elif user.role == "customer":
                return qs.get(id=id, customer_user=user)
            return None
        except Order.DoesNotExist:
            return None

    def get(self, request, id):
        order = self.get_object(id, request.user)
        if not order:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrderDetailSerializer(order, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, id):
        order = self.get_object(id, request.user)
        if not order:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        
        if "size_breakdown" in request.data:
            if not order.is_size_breakdown_editable:
                return Response(
                    {"error": "Size breakdown can only be edited before the order is confirmed."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from .serializers import OrderSizeBreakdownUpdateSerializer
            serializer = OrderSizeBreakdownUpdateSerializer(order, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                detail = OrderDetailSerializer(order, context={"request": request})
                return Response(detail.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        if request.user.role in ("admin", "staff"):
            from .serializers import StaffOrderUpdateSerializer
            serializer = StaffOrderUpdateSerializer(order, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                detail = OrderDetailSerializer(order, context={"request": request})
                return Response(detail.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        return Response({"error": "Only staff members can update general order details."}, status=status.HTTP_403_FORBIDDEN)


# ── UPDATE ORDER STATUS (Admin only) ──────────────────────────────────

class OrderStatusUpdateView(APIView):
    """
    PATCH /api/orders/<id>/status/
    Admin only — update stage and add to timeline.
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
            new_status     = serializer.validated_data["status"]
            notes          = serializer.validated_data.get("notes", "")
            payment_amount = serializer.validated_data.get("payment_amount")
            total_amount   = serializer.validated_data.get("total_amount")
            advance_amount = serializer.validated_data.get("advance_amount")

            update_fields = ["status", "updated_at"]
            order.status  = new_status

            if total_amount is not None:
                order.total_amount = total_amount
                update_fields.append("total_amount")
            if advance_amount is not None:
                order.advance_amount = advance_amount
                update_fields.append("advance_amount")

            # Calculate active payment amount
            if order.status == "advance_pending" and order.advance_amount is not None:
                order.payment_amount = order.advance_amount
                if "payment_amount" not in update_fields:
                    update_fields.append("payment_amount")
            elif order.status == "payment_pending" and order.total_amount is not None and order.advance_amount is not None:
                order.payment_amount = order.total_amount - order.advance_amount
                if "payment_amount" not in update_fields:
                    update_fields.append("payment_amount")
            elif payment_amount is not None:
                order.payment_amount = payment_amount
                update_fields.append("payment_amount")

            unit_price     = serializer.validated_data.get("unit_price")
            hsn_code       = serializer.validated_data.get("hsn_code")
            gst_percentage = serializer.validated_data.get("gst_percentage")
            tracking_link  = serializer.validated_data.get("tracking_link")
            tracking_code  = serializer.validated_data.get("tracking_code")

            if unit_price is not None:
                order.unit_price = unit_price
                update_fields.append("unit_price")
            if hsn_code is not None:
                order.hsn_code = hsn_code
                update_fields.append("hsn_code")
            if gst_percentage is not None:
                order.gst_percentage = gst_percentage
                update_fields.append("gst_percentage")
            if tracking_link is not None:
                order.tracking_link = tracking_link
                update_fields.append("tracking_link")
            if tracking_code is not None:
                order.tracking_code = tracking_code
                update_fields.append("tracking_code")

            order.save(update_fields=update_fields)

            OrderStageHistory.objects.create(
                order      = order,
                stage      = new_status,
                changed_by = request.user,
                notes      = notes,
            )

            # Auto-create Razorpay payment when status → advance_pending / payment_pending
            if order.status == "advance_pending" and order.advance_amount:
                try:
                    from payments import gateway
                    gateway.check_and_create_advance_payment(order)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(
                        f"Advance payment creation failed for {order.order_number}: {e}"
                    )
            elif order.status == "payment_pending":
                try:
                    from payments import gateway
                    gateway.check_and_create_final_payment(order)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(
                        f"Final payment creation failed for {order.order_number}: {e}"
                    )

            # Send stage notification to customer
            try:
                from notifications.service import send_order_stage_notification
                send_order_stage_notification(order, new_status)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"Notification failed for {order.order_number}: {e}"
                )

            detail = OrderDetailSerializer(order, context={"request": request})
            return Response(detail.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── ORDER NOTES ────────────────────────────────────────────────────────

class OrderNotesView(APIView):
    """
    GET  /api/orders/<uuid>/notes/  — list all notes
    POST /api/orders/<uuid>/notes/  — add a note
    """
    permission_classes = [IsAuthenticated]

    def get_order(self, id, user):
        from .models import Order
        try:
            if user.role in ("admin", "staff"):
                return Order.objects.get(id=id)
            elif user.role == "customer":
                return Order.objects.get(id=id, customer_user=user)
            return None
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


# ── STAFF: PLACE ORDER ON BEHALF OF CUSTOMER ──────────────────────────

class StaffOrderCreateView(APIView):
    """
    POST /api/orders/staff/wl/      — Staff places White Label order for a customer
    POST /api/orders/staff/pl/      — Staff places Private Label order for a customer
    IMAGE UPLOAD is done via multipart.
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    SERIALIZER_MAP = {
        "wl":      StaffWLOrderCreateSerializer,
        "pl":      StaffPLOrderCreateSerializer,
        "fabrics": StaffFabricsOrderCreateSerializer,
    }

    def post(self, request, order_type):
        serializer_class = self.SERIALIZER_MAP.get(order_type)
        if not serializer_class:
            return Response(
                {"error": "Invalid order type. Use wl, pl, or fabrics."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(request.data, "dict"):
            data = request.data.dict()
        else:
            data = dict(request.data)
        images_data = request.FILES.getlist("images")
        data["images"] = images_data

        serializer = serializer_class(
            data    = data,
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


# ── ORDER INVOICE ──────────────────────────────────────────────────────

class OrderInvoiceView(APIView):
    """
    GET /api/orders/<uuid>/invoice/
    Returns a branded PDF invoice.
    Can be type=advance or type=final.
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        # ── Fetch order ────────────────────────────────────────────────
        try:
            qs = Order.objects.select_related(
                "customer_user",
                "customer_user__customer_profile",
                "white_label_catalogue",
                "fabric_catalogue",
            ).prefetch_related("stage_history")

            if request.user.role in ("admin", "staff"):
                order = qs.get(id=id)
            elif request.user.role == "customer":
                order = qs.get(id=id, customer_user=request.user)
            else:
                return Response({"error": "Access denied."}, status=403)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=404)

        invoice_type = request.query_params.get("type", "final")

        if invoice_type == "advance":
            allowed_statuses = {
                "advance_paid", "bulk_production", "quality_inspection", "packing",
                "payment_pending", "payment_done", "dispatch", "shipment_tracking", "delivered"
            }
            if order.status not in allowed_statuses:
                return Response(
                    {"error": "Advance invoice is only available after advance payment is completed."},
                    status=400,
                )
        else:
            if order.status not in ("payment_done", "dispatch", "shipment_tracking", "delivered"):
                return Response(
                    {"error": "Final invoice is only available after final payment is completed."},
                    status=400,
                )

        # ── Fetch payment transaction ──────────────────────────────────
        from payments.models import PaymentTransaction
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(order)
        
        if invoice_type == "advance":
            transaction = PaymentTransaction.objects.filter(
                content_type=ct,
                object_id=order.id,
                status="paid",
                notes__icontains="advance",
            ).order_by("-paid_at").first()
        else:
            transaction = PaymentTransaction.objects.filter(
                content_type=ct,
                object_id=order.id,
                status="paid",
            ).exclude(notes__icontains="advance").order_by("-paid_at").first()

        # ── Fetch customer profile ─────────────────────────────────────
        try:
            profile = order.customer_user.customer_profile
        except Exception:
            profile = None

        # ── Generate & return PDF ──────────────────────────────────────
        from huezo_backend.utils.zoho import ZohoBooksClient
        try:
            zoho_client = ZohoBooksClient()
            if invoice_type == "advance":
                invoice_id = order.zoho_advance_invoice_id
                if not invoice_id:
                    invoice_id = zoho_client.create_invoice(order, invoice_type="advance")
            else:
                invoice_id = order.zoho_final_invoice_id
                if not invoice_id:
                    invoice_id = zoho_client.create_invoice(order, invoice_type="final")
            pdf_bytes = zoho_client.get_invoice_pdf(invoice_id)
        except Exception as e:
            import logging
            logging.getLogger("orders.views").warning(
                f"Zoho Invoice PDF retrieval failed for {order.order_number}: {e}. Falling back to local PDF."
            )
            pdf_bytes = generate_invoice_pdf(order, transaction, profile, invoice_type=invoice_type)

        response  = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="Invoice-{order.order_number}.pdf"'
        )
        return response


# ── ASSIGN STAFF TO ORDER ──────────────────────────────────────────────

class OrderAssignView(APIView):
    """
    PATCH /api/orders/<uuid>/assign/
    Admin only — assign or unassign a staff/admin member to an order.
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def patch(self, request, id):
        try:
            order = Order.objects.get(id=id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        previous_assignee = order.assigned_to
        order.assigned_to = serializer.validated_data["assigned_to"]
        order.save(update_fields=["assigned_to", "updated_at"])

        assigned = order.assigned_to

        # Notify the newly assigned staff member
        if assigned and assigned != previous_assignee:
            try:
                from notifications.service import send_order_assigned_notification
                send_order_assigned_notification(
                    order            = order,
                    assigned_to_user = assigned,
                    assigned_by_user = request.user,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"Assignment notification failed for {order.order_number}: {e}"
                )

        return Response({
            "message": "Staff assigned successfully." if assigned else "Order unassigned.",
            "order_id": str(order.id),
            "order_number": order.order_number,
            "assigned_to": {
                "id": str(assigned.id),
                "email": assigned.email,
                "role": assigned.role,
            } if assigned else None,
        })


class OrderCancelView(APIView):
    """
    POST /api/orders/<uuid>/cancel/
    Allows customer or staff to cancel the order before the advance is paid.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        from payments.models import PaymentTransaction, PaymentStatus
        from django.contrib.contenttypes.models import ContentType

        try:
            if request.user.role in ("admin", "staff"):
                order = Order.objects.get(id=id)
            elif request.user.role == "customer":
                order = Order.objects.get(id=id, customer_user=request.user)
            else:
                return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        # Cancellation is only allowed before advance is paid
        # Check 1: Must not be in progress / paid stages
        not_allowed_cancel_statuses = {
            "advance_paid", "bulk_production", "quality_inspection", "packing",
            "payment_pending", "payment_done", "dispatch", "shipment_tracking", "delivered"
        }
        if order.status in not_allowed_cancel_statuses:
            return Response(
                {"error": "Order cannot be cancelled because it is already in progress or completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check 2: Must not have any paid transaction
        ct = ContentType.objects.get_for_model(order)
        if PaymentTransaction.objects.filter(
            content_type=ct,
            object_id=order.id,
            status=PaymentStatus.PAID,
        ).exists():
            return Response(
                {"error": "Order cannot be cancelled because the advance payment has already been made."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cancel order
        order.status = "cancelled"
        order.payment_amount = None
        order.save(update_fields=["status", "payment_amount", "updated_at"])

        OrderStageHistory.objects.create(
            order      = order,
            stage      = "cancelled",
            changed_by = request.user,
            notes      = f"Order cancelled by {request.user.role} ({request.user.email}).",
        )

        return Response({"status": "ok", "message": "Order has been cancelled successfully."})


# ── ORDER PO SUMMARY ──────────────────────────────────────────────────

class OrderPOSummaryView(APIView):
    """
    GET /api/orders/<uuid>/po-summary/
    Returns a branded PDF Purchase Order Summary.
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        try:
            qs = Order.objects.select_related(
                "customer_user",
                "customer_user__customer_profile",
                "white_label_catalogue",
                "fabric_catalogue",
            )
            if request.user.role in ("admin", "staff"):
                order = qs.get(id=id)
            elif request.user.role == "customer":
                order = qs.get(id=id, customer_user=request.user)
            else:
                return Response({"error": "Access denied."}, status=403)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=404)

        if not order.is_po_summary_available:
            return Response(
                {"error": "PO Summary is not generated yet. It is generated once the order reaches the confirmed stage."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = order.customer_user.customer_profile
        except Exception:
            profile = None

        # ── Fetch or Create Zoho Sales Order & Fetch PDF ────────────────
        from huezo_backend.utils.zoho import ZohoBooksClient
        try:
            zoho_client = ZohoBooksClient()
            so_id = order.zoho_po_id
            if not so_id:
                so_id = zoho_client.create_sales_order(order)
            pdf_bytes = zoho_client.get_sales_order_pdf(so_id)
        except Exception as e:
            import logging
            logging.getLogger("orders.views").warning(
                f"Zoho Sales Order PDF retrieval failed for {order.order_number}: {e}. Falling back to local PDF."
            )
            pdf_bytes = generate_po_summary_pdf(order, profile)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="PO-Summary-{order.order_number}.pdf"'
        )
        return response