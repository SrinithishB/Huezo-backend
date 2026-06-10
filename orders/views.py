# orders/views.py

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
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


# ── FILTER ─────────────────────────────────────────────────────────────

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
            "customer_user", "white_label_catalogue", "fabric_catalogue", "assigned_to",
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

            if request.user.role == "customer":
                order = qs.get(id=id, customer_user=request.user)
            else:
                order = qs.get(id=id)
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
            pdf_bytes = _generate_invoice_pdf(order, transaction, profile, invoice_type=invoice_type)

        response  = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="Invoice-{order.order_number}.pdf"'
        )
        return response


# ── PDF GENERATION ─────────────────────────────────────────────────────

def _generate_invoice_pdf(order, transaction, profile, invoice_type="final"):
    """
    Build a branded A4 TAX INVOICE or ADVANCE RECEIPT PDF using ReportLab.
    Matches reference format: logo, GST table with CGST/SGST breakdown.
    """
    from io import BytesIO
    from decimal import Decimal, ROUND_HALF_UP
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable, Image,
    )
    from django.conf import settings as django_settings
    import os

    # ── Colours ────────────────────────────────────────────────────────
    C_DARK   = colors.HexColor("#1C0A0C")
    C_BURNT  = colors.HexColor("#341417")
    C_STROKE = colors.HexColor("#EDE8E3")
    C_MUTED  = colors.HexColor("#8A7F7A")
    C_WARM   = colors.HexColor("#F3EDE6")
    C_GREEN  = colors.HexColor("#2E9E55")
    C_WHITE  = colors.white
    C_SUB    = colors.HexColor("#E5C5C8")
    C_LIGHT  = colors.HexColor("#F9F5F2")

    # ── Helpers ────────────────────────────────────────────────────────
    def humanise(s):
        return s.replace("_", " ").title() if s else "—"

    def fmt_date(dt):
        if not dt:
            return "—"
        try:
            from django.utils import timezone
            return timezone.localtime(dt).strftime("%d/%m/%Y")
        except Exception:
            return str(dt)

    def ps(name, **kwargs):
        return ParagraphStyle(name, **kwargs)

    # ── GST Calculations ───────────────────────────────────────────────
    gst_pct      = Decimal(str(order.gst_percentage)) if order.gst_percentage else Decimal("5")
    half_gst     = gst_pct / 2

    if invoice_type == "advance":
        total_round  = Decimal(str(order.advance_amount)) if order.advance_amount else Decimal("0")
        subtotal     = (total_round / (Decimal("1") + gst_pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cgst_amt     = (subtotal * half_gst / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst_amt     = (total_round - subtotal - cgst_amt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_exact  = total_round
        rounding_adj = Decimal("0")
    else:
        qty          = Decimal(str(order.total_quantity))
        unit_price   = Decimal(str(order.unit_price))   if order.unit_price   else Decimal("0")
        subtotal     = (unit_price * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cgst_amt     = (subtotal * half_gst / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst_amt     = (subtotal * half_gst / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_exact  = subtotal + cgst_amt + sgst_amt
        total_round  = total_exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        rounding_adj = total_round - total_exact

    # ── Document setup ─────────────────────────────────────────────────
    buffer = BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm,  bottomMargin=15*mm,
    )
    W     = doc.width
    story = []

    s_body  = ps("body",  fontSize=9,  fontName="Helvetica",      textColor=C_DARK,  leading=13)
    s_muted = ps("muted", fontSize=8,  fontName="Helvetica",      textColor=C_MUTED, leading=12)
    s_bold  = ps("bold",  fontSize=9,  fontName="Helvetica-Bold", textColor=C_DARK,  leading=13)
    s_right = ps("right", fontSize=9,  fontName="Helvetica",      textColor=C_DARK,  alignment=TA_RIGHT)
    s_rbold = ps("rbold", fontSize=9,  fontName="Helvetica-Bold", textColor=C_DARK,  alignment=TA_RIGHT)

    def th(align=TA_LEFT):
        return ps(f"th{align}", fontSize=8, fontName="Helvetica-Bold",
                  textColor=C_WHITE, alignment=align)

    # ══════════════════════════════════════════════════════════════════
    #  HEADER — Logo left, TAX INVOICE right
    # ══════════════════════════════════════════════════════════════════
    logo_path = os.path.join(django_settings.BASE_DIR, "static", "images", "logo.png")
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=28*mm, height=28*mm, kind="proportional")
        logo_cell = logo_img
    else:
        logo_cell = Paragraph("<b>HUEZO</b>",
                              ps("fb", fontSize=20, fontName="Helvetica-Bold", textColor=C_BURNT))

    title_text = "ADVANCE RECEIPT" if invoice_type == "advance" else "TAX INVOICE"
    hdr = Table([[
        logo_cell,
        Table([[
            Paragraph(f"<b>{title_text}</b>",
                      ps("ti", fontSize=20, fontName="Helvetica-Bold",
                         textColor=C_BURNT, alignment=TA_RIGHT)),
        ]], colWidths=[W * 0.6]),
    ]], colWidths=[W * 0.4, W * 0.6])
    hdr.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width="100%", thickness=2, color=C_BURNT))
    story.append(Spacer(1, 4*mm))

    # ══════════════════════════════════════════════════════════════════
    #  COMPANY INFO + INVOICE META (two columns)
    # ══════════════════════════════════════════════════════════════════
    paid_at  = fmt_date(transaction.paid_at) if transaction else "—"
    pay_ref  = (transaction.payment_reference or "—") if transaction else "—"

    company_lines = [
        Paragraph("<b>HUEZO Fashion Manufacturing</b>",
                  ps("cn", fontSize=10, fontName="Helvetica-Bold", textColor=C_DARK)),
        Paragraph("huezo.in  |  support@huezo.in",  s_muted),
    ]

    meta_rows = [
        ("#",             order.order_number),
        ("Invoice Date",  paid_at),
        ("Terms",         "Due on Receipt"),
        ("Due Date",      paid_at),
        ("Place Of Supply", "Tamil Nadu (33)"),
    ]
    meta_tbl = Table(
        [[Paragraph(k, s_muted), Paragraph(v, s_bold)] for k, v in meta_rows],
        colWidths=[30*mm, W/2 - 34*mm],
    )
    meta_tbl.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
    ]))

    info_col = Table([[p] for p in company_lines], colWidths=[W/2 - 4*mm])
    top_row  = Table([[info_col, meta_tbl]], colWidths=[W/2, W/2])
    top_row.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    story.append(top_row)
    story.append(Spacer(1, 4*mm))

    # ══════════════════════════════════════════════════════════════════
    #  BILL TO / SHIP TO
    # ══════════════════════════════════════════════════════════════════
    brand_name   = getattr(profile, "brand_name",   None) or ""
    contact_name = getattr(profile, "contact_name", None) or ""
    phone        = getattr(profile, "phone",        None) or ""
    address      = ""
    if profile:
        try:
            fa = profile.full_address
            address = fa() if callable(fa) else (fa or "")
        except Exception:
            pass

    def addr_block(title):
        rows = [[Paragraph(f"<b>{title}</b>",
                           ps(title, fontSize=9, fontName="Helvetica-Bold", textColor=C_WHITE))]]
        if brand_name:
            rows.append([Paragraph(f"<b>{brand_name}</b>", s_bold)])
        if contact_name:
            rows.append([Paragraph(contact_name, s_body)])
        if address:
            rows.append([Paragraph(address, s_muted)])
        if phone:
            rows.append([Paragraph(phone, s_body)])
        tbl = Table(rows, colWidths=[W/2 - 4*mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  C_BURNT),
            ("TOPPADDING",    (0, 0), (-1, 0),  6),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 1), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_STROKE),
        ]))
        return tbl

    addr_row = Table([[addr_block("Bill To"), addr_block("Ship To")]],
                     colWidths=[W/2, W/2])
    addr_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",  (1, 0), (1, -1),  4),
    ]))
    story.append(addr_row)
    story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  ITEMS TABLE  with HSN / Qty / Rate / CGST / SGST / Amount
    # ══════════════════════════════════════════════════════════════════
    unit = "meters" if order.order_type == "fabrics" else "pcs"

    # Build description string
    desc_suffix = " (Advance Payment)" if invoice_type == "advance" else ""
    desc_parts = [humanise(order.order_type) + desc_suffix]
    if order.garment_type:
        desc_parts.append(order.garment_type)
    if order.style_name:
        desc_parts.append(order.style_name)
    if order.white_label_catalogue:
        desc_parts.append(f"Prototype: {order.white_label_catalogue.prototype_code}")
    if order.fabric_catalogue:
        desc_parts.append(f"Fabric: {order.fabric_catalogue.fabric_name}")
    if order.size_breakdown:
        try:
            import json
            sizes = order.size_breakdown
            if isinstance(sizes, str):
                sizes = json.loads(sizes)
            for sb in sizes:
                desc_parts.append(f"as per dc: {sb.get('size','?')} - {sb.get('quantity','?')} {unit}")
        except Exception:
            pass
    desc_str = "\n".join(desc_parts)

    hsn = order.hsn_code or "—"

    # Column widths: #, Description, HSN, Qty, Rate, CGST%, CGSTAmt, SGST%, SGSTAmt, Amount
    cw = [8*mm, W-148*mm, 18*mm, 16*mm, 20*mm, 12*mm, 20*mm, 12*mm, 20*mm, 22*mm]

    header_row = [
        Paragraph("<b>#</b>",           th()),
        Paragraph("<b>Item &amp; Description</b>", th()),
        Paragraph("<b>HSN/SAC</b>",     th(TA_CENTER)),
        Paragraph("<b>Qty</b>",         th(TA_RIGHT)),
        Paragraph("<b>Rate</b>",        th(TA_RIGHT)),
        Paragraph(f"<b>CGST%</b>",      th(TA_CENTER)),
        Paragraph("<b>CGST Amt</b>",    th(TA_RIGHT)),
        Paragraph(f"<b>SGST%</b>",      th(TA_CENTER)),
        Paragraph("<b>SGST Amt</b>",    th(TA_RIGHT)),
        Paragraph("<b>Amount</b>",      th(TA_RIGHT)),
    ]

    if invoice_type == "advance":
        qty_val = Decimal("1.00")
        rate_val = subtotal
    else:
        qty_val = Decimal(str(order.total_quantity))
        rate_val = Decimal(str(order.unit_price)) if order.unit_price else Decimal("0")

    data_row = [
        Paragraph("1",                                   s_body),
        Paragraph(desc_str.replace("\n", "<br/>"),       s_muted),
        Paragraph(hsn,                                   ps("hc", fontSize=8, fontName="Helvetica", textColor=C_DARK, alignment=TA_CENTER)),
        Paragraph(f"{qty_val:.2f}",                      s_right),
        Paragraph(f"{rate_val:,.2f}",                    s_right),
        Paragraph(f"{half_gst:.1f}%",                    ps("cp", fontSize=8, fontName="Helvetica", textColor=C_DARK, alignment=TA_CENTER)),
        Paragraph(f"{cgst_amt:,.2f}",                    s_right),
        Paragraph(f"{half_gst:.1f}%",                    ps("sp", fontSize=8, fontName="Helvetica", textColor=C_DARK, alignment=TA_CENTER)),
        Paragraph(f"{sgst_amt:,.2f}",                    s_right),
        Paragraph(f"{subtotal:,.2f}",                    s_rbold),
    ]

    items_tbl = Table([header_row, data_row], colWidths=cw, repeatRows=1)
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_BURNT),
        ("TOPPADDING",    (0, 0), (-1, 0),  7),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("BACKGROUND",    (0, 1), (-1, -1), C_WARM),
        ("TOPPADDING",    (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, C_STROKE),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_STROKE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, C_STROKE),
    ]))
    story.append(items_tbl)
    story.append(Spacer(1, 3*mm))

    # ══════════════════════════════════════════════════════════════════
    #  TOTALS — Items count left, breakdown right
    # ══════════════════════════════════════════════════════════════════
    items_count = Paragraph(
        f"Items in Total {qty_val:.2f}",
        ps("ic", fontSize=9, fontName="Helvetica-Bold", textColor=C_DARK),
    )

    if invoice_type == "advance":
        total_rows = [
            ("Sub Total",                      f"{subtotal:,.2f}",      False),
            (f"CGST ({half_gst}%)",            f"{cgst_amt:,.2f}",     False),
            (f"SGST ({half_gst}%)",            f"{sgst_amt:,.2f}",     False),
            ("Total (Advance Paid)",            f"Rs.{total_round:,.2f}", True),
            ("Balance Due",                     "Rs.0.00", True),
        ]
    else:
        advance_paid = Decimal(str(order.advance_amount)) if order.advance_amount else Decimal("0")
        final_balance_paid = total_round - advance_paid
        total_rows = [
            ("Sub Total",                      f"{subtotal:,.2f}",      False),
            (f"CGST ({half_gst}%)",            f"{cgst_amt:,.2f}",     False),
            (f"SGST ({half_gst}%)",            f"{sgst_amt:,.2f}",     False),
            ("Rounding",                        f"{rounding_adj:+.2f}", False),
            ("Total Order Amount",              f"Rs.{total_round:,.2f}", True),
            ("Less: Advance Paid",              f"Rs.{advance_paid:,.2f}", False),
            ("Final Balance Paid",              f"Rs.{final_balance_paid:,.2f}", True),
            ("Balance Due",                     "Rs.0.00", True),
        ]

    tr_data = []
    for label, value, bold in total_rows:
        fn = "Helvetica-Bold" if bold else "Helvetica"
        fs = 10 if bold else 9
        tr_data.append([
            Paragraph(label, ps(f"tl{label}", fontSize=fs, fontName=fn,
                                textColor=C_DARK, alignment=TA_RIGHT)),
            Paragraph(value, ps(f"tv{label}", fontSize=fs, fontName=fn,
                                textColor=C_GREEN if bold else C_DARK, alignment=TA_RIGHT)),
        ])

    totals_tbl = Table(tr_data, colWidths=[40*mm, 32*mm])
    
    t_style = [
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for idx, (label, _, bold) in enumerate(total_rows):
        if bold:
            t_style.append(("LINEABOVE", (0, idx), (-1, idx), 1 if label.startswith("Total") or label.startswith("Final") else 0.5, C_STROKE))
        elif label.startswith("Less"):
            t_style.append(("LINEABOVE", (0, idx), (-1, idx), 0.5, C_STROKE))
    totals_tbl.setStyle(TableStyle(t_style))

    total_outer = Table(
        [[items_count, totals_tbl]],
        colWidths=[W - 76*mm, 76*mm],
    )
    total_outer.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    story.append(total_outer)
    story.append(Spacer(1, 4*mm))

    # ── Total in words ────────────────────────────────────────────────
    try:
        from num2words import num2words
        words = num2words(int(total_round), lang="en_IN").title()
        words_str = f"Indian Rupee {words} Only"
    except Exception:
        words_str = f"Rs. {total_round:,.2f}"

    story.append(Paragraph(f"<b>Total In Words</b>", s_muted))
    story.append(Paragraph(f"<i>{words_str}</i>", s_body))
    story.append(Spacer(1, 4*mm))

    # ── Authorized Signature ──────────────────────────────────────────
    sig_tbl = Table([[
        Spacer(1, 1),
        Paragraph("Authorized Signature",
                  ps("sig", fontSize=9, fontName="Helvetica", textColor=C_MUTED, alignment=TA_RIGHT)),
    ]], colWidths=[W - 50*mm, 50*mm])
    sig_tbl.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 6*mm))

    # ══════════════════════════════════════════════════════════════════
    #  PAYMENT RECEIVED BANNER
    # ══════════════════════════════════════════════════════════════════
    banner_text = "&#10003;  ADVANCE PAYMENT RECEIVED" if invoice_type == "advance" else "&#10003;  PAYMENT RECEIVED"
    banner = Table(
        [[Paragraph(
            banner_text,
            ps("paid", fontSize=11, fontName="Helvetica-Bold",
               textColor=C_GREEN, alignment=TA_CENTER),
        )]],
        colWidths=[W],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F0FFF6")),
        ("BOX",           (0, 0), (-1, -1), 1, colors.HexColor("#A8E6BF")),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(banner)
    story.append(Spacer(1, 6*mm))

    # ══════════════════════════════════════════════════════════════════
    #  FOOTER
    # ══════════════════════════════════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=1, color=C_STROKE))
    story.append(Spacer(1, 3*mm))
    footer = Table([[
        Paragraph("HUEZO — Fashion Manufacturing",
                  ps("f1", fontSize=8, fontName="Helvetica-Bold", textColor=C_MUTED)),
        Paragraph("huezo.in  |  support@huezo.in",
                  ps("f2", fontSize=8, fontName="Helvetica",
                     textColor=C_MUTED, alignment=TA_RIGHT)),
    ]], colWidths=[W / 2, W / 2])
    footer.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(footer)

    doc.build(story)
    return buffer.getvalue()


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
            if request.user.role == "customer":
                order = Order.objects.get(id=id, customer_user=request.user)
            else:
                order = Order.objects.get(id=id)
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
            if request.user.role == "customer":
                order = qs.get(id=id, customer_user=request.user)
            else:
                order = qs.get(id=id)
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
            pdf_bytes = _generate_po_summary_pdf(order, profile)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="PO-Summary-{order.order_number}.pdf"'
        )
        return response


def _generate_po_summary_pdf(order, profile):
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable, Image,
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    from django.conf import settings as django_settings
    import os

    # ── Colours ────────────────────────────────────────────────────────
    C_DARK   = colors.HexColor("#1C0A0C")
    C_BURNT  = colors.HexColor("#341417")
    C_STROKE = colors.HexColor("#EDE8E3")
    C_MUTED  = colors.HexColor("#8A7F7A")
    C_WARM   = colors.HexColor("#F3EDE6")
    C_GREEN  = colors.HexColor("#2E9E55")
    C_WHITE  = colors.white
    C_LIGHT  = colors.HexColor("#F9F5F2")

    # ── Helpers ────────────────────────────────────────────────────────
    def humanise(s):
        return s.replace("_", " ").title() if s else "—"

    def fmt_date(dt):
        if not dt:
            return "—"
        try:
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return str(dt)

    def ps(name, **kwargs):
        return ParagraphStyle(name, **kwargs)

    # ── Document setup ─────────────────────────────────────────────────
    buffer = BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm,  bottomMargin=15*mm,
    )
    W     = doc.width
    story = []

    s_body  = ps("body",  fontSize=9,  fontName="Helvetica",      textColor=C_DARK,  leading=13)
    s_muted = ps("muted", fontSize=8,  fontName="Helvetica",      textColor=C_MUTED, leading=12)
    s_bold  = ps("bold",  fontSize=9,  fontName="Helvetica-Bold", textColor=C_DARK,  leading=13)
    s_right = ps("right", fontSize=9,  fontName="Helvetica",      textColor=C_DARK,  alignment=TA_RIGHT)
    s_rbold = ps("rbold", fontSize=9,  fontName="Helvetica-Bold", textColor=C_DARK,  alignment=TA_RIGHT)

    def th(align=TA_LEFT):
        return ps(f"th{align}", fontSize=8, fontName="Helvetica-Bold",
                  textColor=C_WHITE, alignment=align)

    # ══════════════════════════════════════════════════════════════════
    #  HEADER — Logo left, PO SUMMARY right
    # ══════════════════════════════════════════════════════════════════
    logo_path = os.path.join(django_settings.BASE_DIR, "static", "images", "logo.png")
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=28*mm, height=28*mm, kind="proportional")
        logo_cell = logo_img
    else:
        logo_cell = Paragraph("<b>HUEZO</b>",
                               ps("fb", fontSize=20, fontName="Helvetica-Bold", textColor=C_BURNT))

    hdr = Table([[
        logo_cell,
        Table([[
            Paragraph("<b>PO SUMMARY</b>",
                      ps("ti", fontSize=20, fontName="Helvetica-Bold",
                         textColor=C_BURNT, alignment=TA_RIGHT)),
        ]], colWidths=[W * 0.6]),
    ]], colWidths=[W * 0.4, W * 0.6])
    hdr.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width="100%", thickness=2, color=C_BURNT))
    story.append(Spacer(1, 4*mm))

    # ══════════════════════════════════════════════════════════════════
    #  COMPANY INFO + ORDER META (two columns)
    # ══════════════════════════════════════════════════════════════════
    company_lines = [
        Paragraph("<b>HUEZO Fashion Manufacturing</b>",
                  ps("cn", fontSize=10, fontName="Helvetica-Bold", textColor=C_DARK)),
        Paragraph("huezo.in  |  support@huezo.in",  s_muted),
    ]

    meta_rows = [
        ("PO Number",     order.order_number),
        ("PO Date",       fmt_date(order.created_at)),
        ("Order Type",    humanise(order.order_type)),
    ]
    if order.garment_type:
        meta_rows.append(("Garment", order.garment_type))
    if order.for_category:
        meta_rows.append(("Category", humanise(order.for_category)))

    meta_tbl = Table(
        [[Paragraph(k, s_muted), Paragraph(v, s_bold)] for k, v in meta_rows],
        colWidths=[30*mm, W/2 - 34*mm],
    )
    meta_tbl.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
    ]))

    info_col = Table([[p] for p in company_lines], colWidths=[W/2 - 4*mm])
    top_row  = Table([[info_col, meta_tbl]], colWidths=[W/2, W/2])
    top_row.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    story.append(top_row)
    story.append(Spacer(1, 4*mm))

    # ══════════════════════════════════════════════════════════════════
    #  CUSTOMER INFO
    # ══════════════════════════════════════════════════════════════════
    brand_name   = getattr(profile, "brand_name",   None) or ""
    contact_name = getattr(profile, "contact_name", None) or ""
    phone        = getattr(profile, "phone",        None) or ""
    address      = ""
    if profile:
        try:
            fa = profile.full_address
            address = fa() if callable(fa) else (fa or "")
        except Exception:
            pass

    def addr_block(title):
        rows = [[Paragraph(f"<b>{title}</b>",
                           ps(title, fontSize=9, fontName="Helvetica-Bold", textColor=C_WHITE))]]
        if brand_name:
            rows.append([Paragraph(f"<b>{brand_name}</b>", s_bold)])
        if contact_name:
            rows.append([Paragraph(contact_name, s_body)])
        if address:
            rows.append([Paragraph(address, s_muted)])
        if phone:
            rows.append([Paragraph(phone, s_body)])
        tbl = Table(rows, colWidths=[W/2 - 4*mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  C_BURNT),
            ("TOPPADDING",    (0, 0), (-1, 0),  6),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 1), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_STROKE),
        ]))
        return tbl

    addr_row = Table([[addr_block("Bill To"), addr_block("Ship To")]],
                     colWidths=[W/2, W/2])
    addr_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",  (1, 0), (1, -1),  4),
    ]))
    story.append(addr_row)
    story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  ORDER SPECIFICATIONS
    # ══════════════════════════════════════════════════════════════════
    specs_data = []
    
    if order.order_type == "white_label" and order.white_label_catalogue:
        specs_data.append([Paragraph("Prototype Code", s_muted), Paragraph(order.white_label_catalogue.prototype_code, s_bold)])
    elif order.order_type == "fabrics" and order.fabric_catalogue:
        specs_data.append([Paragraph("Fabric Catalogue", s_muted), Paragraph(order.fabric_catalogue.fabric_name, s_bold)])
    
    if order.style_name:
        specs_data.append([Paragraph("Style Name", s_muted), Paragraph(order.style_name, s_bold)])
        
    specs_data.append([Paragraph("Total Quantity", s_muted), Paragraph(f"{order.total_quantity} {'meters' if order.order_type == 'fabrics' else 'pcs'}", s_bold)])
    
    if order.moq:
        specs_data.append([Paragraph("MOQ Requirement", s_muted), Paragraph(str(order.moq), s_body)])

    if order.order_type == "fabrics":
        specs_data.append([Paragraph("Swatch Required", s_muted), Paragraph("Yes" if order.swatch_required else "No", s_body)])

    if order.customization_notes:
        specs_data.append([Paragraph("Customization Notes", s_muted), Paragraph(order.customization_notes, s_body)])

    if order.message:
        specs_data.append([Paragraph("Fabric Sourcing Message", s_muted), Paragraph(order.message, s_body)])

    specs_table = Table(specs_data, colWidths=[50*mm, W - 50*mm])
    specs_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.5, C_STROKE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))

    story.append(Paragraph("<b>Order Specifications</b>", ps("sh", fontSize=11, fontName="Helvetica-Bold", textColor=C_BURNT)))
    story.append(Spacer(1, 2*mm))
    story.append(specs_table)
    story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  SIZE BREAKDOWN TABLE
    # ══════════════════════════════════════════════════════════════════
    if order.size_breakdown:
        size_headers = [Paragraph("<b>Size</b>", th(TA_CENTER)), Paragraph("<b>Quantity (pcs)</b>", th(TA_CENTER))]
        size_rows = [size_headers]
        
        for item in order.size_breakdown:
            if not isinstance(item, dict):
                continue
            size_val = str(item.get("size", "")).replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip()
            qty_val = str(item.get("quantity", 0))
            size_rows.append([
                Paragraph(size_val, ps("szc", fontSize=9, fontName="Helvetica-Bold", alignment=TA_CENTER)),
                Paragraph(qty_val, ps("szq", fontSize=9, fontName="Helvetica", alignment=TA_CENTER))
            ])
            
        size_rows.append([
            Paragraph("<b>Total</b>", ps("szt", fontSize=9, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(f"<b>{order.total_quantity}</b>", ps("sztq", fontSize=9, fontName="Helvetica-Bold", alignment=TA_CENTER))
        ])
        
        size_table = Table(size_rows, colWidths=[W/2, W/2])
        size_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_BURNT),
            ("GRID", (0, 0), (-1, -1), 0.5, C_STROKE),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, -1), (-1, -1), C_WARM),
        ]))
        
        story.append(Paragraph("<b>Size Breakdown</b>", ps("sh2", fontSize=11, fontName="Helvetica-Bold", textColor=C_BURNT)))
        story.append(Spacer(1, 2*mm))
        story.append(size_table)
        story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  FINANCIAL DETAILS
    # ══════════════════════════════════════════════════════════════════
    cost_rows = []
    if order.unit_price:
        cost_rows.append(("Unit Rate", f"Rs. {order.unit_price}"))
    if order.gst_percentage:
        cost_rows.append(("GST Rate", f"{order.gst_percentage}%"))
    if order.total_amount:
        cost_rows.append(("Total Estimated Amount", f"Rs. {order.total_amount}"))
    if order.advance_amount:
        cost_rows.append(("Advance Amount", f"Rs. {order.advance_amount}"))

    if cost_rows:
        cost_table = Table(
            [[Paragraph(k, s_muted), Paragraph(v, s_bold)] for k, v in cost_rows],
            colWidths=[50*mm, W - 50*mm]
        )
        cost_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, C_STROKE),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(Paragraph("<b>Financial Details</b>", ps("sh3", fontSize=11, fontName="Helvetica-Bold", textColor=C_BURNT)))
        story.append(Spacer(1, 2*mm))
        story.append(cost_table)
        story.append(Spacer(1, 6*mm))

    # ══════════════════════════════════════════════════════════════════
    #  TERMS & CONDITIONS
    # ══════════════════════════════════════════════════════════════════
    terms_text = (
        "<b>Terms & Conditions:</b><br/>"
        "This PO Summary is automatically generated based on the order details confirmed by the customer through the Huezo App. "
        "Customers are requested to verify all specifications, quantities, sizes, and shipping details immediately upon receipt. "
        "Any modification request must be submitted to Huezo and may be subject to feasibility, additional charges, and revised delivery timelines. "
        "Production may commence based on this PO Summary, and changes requested after production initiation may not be accommodated. "
        "Failure to report discrepancies within 24 hours shall be deemed acceptance of the PO details."
    )
    story.append(Paragraph(terms_text, ps("terms", fontSize=7, fontName="Helvetica", textColor=C_MUTED, leading=10)))
    story.append(Spacer(1, 4*mm))

    # ══════════════════════════════════════════════════════════════════
    #  FOOTER
    # ══════════════════════════════════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=1, color=C_STROKE))
    story.append(Spacer(1, 3*mm))
    footer = Table([[
        Paragraph("HUEZO — Fashion Manufacturing",
                  ps("f1", fontSize=8, fontName="Helvetica-Bold", textColor=C_MUTED)),
        Paragraph("huezo.in  |  support@huezo.in",
                  ps("f2", fontSize=8, fontName="Helvetica",
                     textColor=C_MUTED, alignment=TA_RIGHT)),
    ]], colWidths=[W / 2, W / 2])
    footer.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(footer)

    doc.build(story)
    return buffer.getvalue()