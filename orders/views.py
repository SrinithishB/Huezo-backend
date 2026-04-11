# orders/views.py

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
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
    OrderListSerializer,
    OrderDetailSerializer,
    OrderStatusUpdateSerializer,
    OrderAssignSerializer,
)
from accounts.permissions import IsAdminOrStaff


# ── FILTER ─────────────────────────────────────────────────────────────

class OrderFilter(django_filters.FilterSet):
    date_from   = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to     = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")
    assigned_to = django_filters.UUIDFilter(field_name="assigned_to__id")
    unassigned  = django_filters.BooleanFilter(field_name="assigned_to", lookup_expr="isnull")

    class Meta:
        model  = Order
        fields = ["order_type", "status", "fabric_type", "for_category", "assigned_to"]


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

            update_fields = ["status", "updated_at"]
            order.status  = new_status

            if payment_amount is not None:
                order.payment_amount = payment_amount
                update_fields.append("payment_amount")

            order.save(update_fields=update_fields)

            OrderStageHistory.objects.create(
                order      = order,
                stage      = new_status,
                changed_by = request.user,
                notes      = notes,
            )

            # Auto-create Razorpay payment when status → payment_pending and amount is set
            if new_status == "payment_pending" and order.payment_amount:
                try:
                    from payments import gateway
                    from payments.models import PaymentTransaction, PaymentStatus
                    from django.contrib.contenttypes.models import ContentType
                    ct = ContentType.objects.get_for_model(order)
                    if not PaymentTransaction.objects.filter(
                        content_type=ct, object_id=order.id, status=PaymentStatus.PENDING
                    ).exists():
                        gateway.create_payment(
                            content_object = order,
                            amount         = order.payment_amount,
                            payment_type   = "order",
                            paid_by        = order.customer_user,
                            notes          = f"Payment for {order.order_number}",
                        )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(
                        f"Payment creation failed for {order.order_number}: {e}"
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
    POST /api/orders/staff/fabrics/ — Staff places Fabrics order for a customer
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    SERIALIZER_MAP = {
        "wl":      StaffWLOrderCreateSerializer,
        "fabrics": StaffFabricsOrderCreateSerializer,
    }

    def post(self, request, order_type):
        serializer_class = self.SERIALIZER_MAP.get(order_type)
        if not serializer_class:
            return Response(
                {"error": "Invalid order type. Use wl or fabrics."},
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


# ── ORDER INVOICE ──────────────────────────────────────────────────────

class OrderInvoiceView(APIView):
    """
    GET /api/orders/<uuid>/invoice/
    Returns a branded PDF invoice.
    Only available once order status is payment_done / dispatch / delivered.
    Customer can only download their own order invoice.
    """
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

        if order.status not in ("payment_done", "dispatch", "delivered"):
            return Response(
                {"error": "Invoice is only available after payment is completed."},
                status=400,
            )

        # ── Fetch payment transaction ──────────────────────────────────
        from payments.models import PaymentTransaction
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(order)
        transaction = PaymentTransaction.objects.filter(
            content_type=ct,
            object_id=order.id,
            status="paid",
        ).order_by("-paid_at").first()

        # ── Fetch customer profile ─────────────────────────────────────
        try:
            profile = order.customer_user.customer_profile
        except Exception:
            profile = None

        # ── Generate & return PDF ──────────────────────────────────────
        pdf_bytes = _generate_invoice_pdf(order, transaction, profile)
        response  = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="Invoice-{order.order_number}.pdf"'
        )
        return response


# ── PDF GENERATION ─────────────────────────────────────────────────────

def _generate_invoice_pdf(order, transaction, profile):
    """
    Build a branded A4 invoice PDF using ReportLab.
    All imports are local so this module loads fine even without reportlab.
    """
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable,
    )

    # ── Colours ────────────────────────────────────────────────────────
    C_DARK   = colors.HexColor("#1C0A0C")
    C_BURNT  = colors.HexColor("#341417")
    C_STROKE = colors.HexColor("#EDE8E3")
    C_MUTED  = colors.HexColor("#8A7F7A")
    C_WARM   = colors.HexColor("#F3EDE6")
    C_GREEN  = colors.HexColor("#2E9E55")
    C_WHITE  = colors.white
    C_SUB    = colors.HexColor("#E5C5C8")

    # ── Helpers ────────────────────────────────────────────────────────
    def humanise(s):
        return s.replace("_", " ").title() if s else "—"

    def fmt_date(dt):
        if not dt:
            return "—"
        try:
            from django.utils import timezone
            return timezone.localtime(dt).strftime("%d %b %Y, %I:%M %p")
        except Exception:
            return str(dt)

    # ── Document setup ─────────────────────────────────────────────────
    buffer = BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm,  bottomMargin=20*mm,
    )
    W     = doc.width
    story = []

    # ── Styles ─────────────────────────────────────────────────────────
    def ps(name, **kwargs):
        return ParagraphStyle(name, **kwargs)

    s_h2    = ps("h2",    fontSize=11, fontName="Helvetica-Bold",  textColor=C_DARK,  spaceAfter=4)
    s_h3    = ps("h3",    fontSize=9,  fontName="Helvetica-Bold",  textColor=C_MUTED, spaceBefore=4, spaceAfter=2)
    s_body  = ps("body",  fontSize=9,  fontName="Helvetica",       textColor=C_DARK,  leading=14)
    s_muted = ps("muted", fontSize=8,  fontName="Helvetica",       textColor=C_MUTED, leading=12)
    s_right = ps("right", fontSize=9,  fontName="Helvetica",       textColor=C_DARK,  alignment=TA_RIGHT)

    def th(align=None):
        kw = dict(fontSize=8, fontName="Helvetica-Bold", textColor=C_WHITE)
        if align:
            kw["alignment"] = align
        return ps(f"th_{id(align)}", **kw)

    # ══════════════════════════════════════════════════════════════════
    #  HEADER — dark band with brand + invoice number
    # ══════════════════════════════════════════════════════════════════
    hdr = Table([[
        Table([[
            Paragraph("<b>HUEZO</b>",
                      ps("br", fontSize=22, fontName="Helvetica-Bold", textColor=C_WHITE)),
            Paragraph("Fashion Manufacturing",
                      ps("bs", fontSize=8,  fontName="Helvetica",       textColor=C_SUB)),
        ]], colWidths=[W * 0.5]),
        Table([[
            Paragraph("INVOICE",
                      ps("it", fontSize=22, fontName="Helvetica-Bold",
                         textColor=C_WHITE, alignment=TA_RIGHT)),
            Paragraph(f"# {order.order_number}",
                      ps("in", fontSize=10, fontName="Helvetica",
                         textColor=C_SUB, alignment=TA_RIGHT)),
        ]], colWidths=[W * 0.5]),
    ]], colWidths=[W * 0.5, W * 0.5])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_BURNT),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (0,  -1), 16),
        ("RIGHTPADDING",  (1, 0), (-1, -1), 16),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 6*mm))

    # ══════════════════════════════════════════════════════════════════
    #  BILLED TO  +  INVOICE DETAILS  (two columns)
    # ══════════════════════════════════════════════════════════════════
    brand_name   = getattr(profile, "brand_name",   None) or ""
    contact_name = getattr(profile, "contact_name", None) or ""
    phone        = getattr(profile, "phone",        None) or ""
    cust_email   = order.customer_user.email

    address = ""
    if profile:
        try:
            fa = profile.full_address
            address = fa() if callable(fa) else (fa or "")
        except Exception:
            pass

    # Left — Billed To
    bill = [[Paragraph("<b>BILLED TO</b>", s_h3)]]
    if brand_name:
        bill.append([Paragraph(f"<b>{brand_name}</b>", s_h2)])
    if contact_name:
        bill.append([Paragraph(contact_name, s_body)])
    bill.append([Paragraph(cust_email, s_body)])
    if phone:
        bill.append([Paragraph(phone, s_body)])
    if address:
        bill.append([Paragraph(address, s_muted)])

    # Right — Invoice meta
    paid_at = fmt_date(transaction.paid_at) if transaction else "—"
    pay_ref = (transaction.payment_reference or "—") if transaction else "—"

    meta_inner = Table(
        [[Paragraph(k, s_muted), Paragraph(v, s_body)] for k, v in [
            ("Order Number", order.order_number),
            ("Order Type",   humanise(order.order_type)),
            ("Payment Date", paid_at),
            ("Payment Ref",  pay_ref),
            ("Status",       humanise(order.status)),
        ]],
        colWidths=[28*mm, W/2 - 32*mm],
    )
    meta_inner.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    two_col = Table([[
        Table(bill,  colWidths=[W/2 - 6*mm]),
        Table([[Paragraph("<b>INVOICE DETAILS</b>", s_h3)], [meta_inner]],
              colWidths=[W/2 - 6*mm]),
    ]], colWidths=[W/2, W/2])
    two_col.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=C_STROKE))
    story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  ORDER SUMMARY TABLE
    # ══════════════════════════════════════════════════════════════════
    story.append(Paragraph("ORDER SUMMARY", s_h3))
    story.append(Spacer(1, 2*mm))

    unit         = "meters" if order.order_type == "fabrics" else "pcs"
    type_label   = humanise(order.order_type)
    detail_parts = []
    if order.white_label_catalogue:
        detail_parts.append(f"Prototype: {order.white_label_catalogue.prototype_code}")
    if order.fabric_catalogue:
        detail_parts.append(f"Fabric: {order.fabric_catalogue.fabric_name}")
    if order.style_name:
        detail_parts.append(f"Style: {order.style_name}")
    if order.garment_type:
        detail_parts.append(f"Garment: {order.garment_type}")
    if order.for_category:
        detail_parts.append(f"Category: {humanise(order.for_category)}")
    detail_str = " · ".join(detail_parts) if detail_parts else type_label

    rows = [[
        Paragraph("<b>Description</b>", th()),
        Paragraph("<b>Details</b>",     th()),
        Paragraph("<b>Qty</b>",         th(TA_RIGHT)),
    ], [
        Paragraph(type_label, s_body),
        Paragraph(detail_str, s_muted),
        Paragraph(f"{order.total_quantity} {unit}", s_right),
    ]]

    # Size breakdown row
    if order.size_breakdown:
        try:
            import json
            sizes = order.size_breakdown
            if isinstance(sizes, str):
                sizes = json.loads(sizes)
            size_str = "  ·  ".join(
                f"{s.get('size', '?')}: {s.get('quantity', '?')}" for s in sizes
            )
            rows.append([
                Paragraph("", s_body),
                Paragraph(f"Sizes — {size_str}", s_muted),
                Paragraph("", s_right),
            ])
        except Exception:
            pass

    items_tbl = Table(rows, colWidths=[45*mm, W - 85*mm, 30*mm])
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_BURNT),
        ("TOPPADDING",    (0, 0), (-1, 0),  8),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  8),
        ("LEFTPADDING",   (0, 0), (-1, 0),  10),
        ("RIGHTPADDING",  (0, 0), (-1, 0),  10),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WARM, C_WHITE]),
        ("TOPPADDING",    (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
        ("LEFTPADDING",   (0, 1), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 1), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, C_STROKE),
    ]))
    story.append(items_tbl)
    story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  PAYMENT TOTAL
    # ══════════════════════════════════════════════════════════════════
    if order.payment_amount:
        totals = [
            ("Subtotal",    f"Rs. {order.payment_amount:,.2f}", False),
            ("Tax (incl.)", "Inclusive",                        False),
            ("TOTAL PAID",  f"Rs. {order.payment_amount:,.2f}", True),
        ]
        total_rows = []
        for label, value, bold in totals:
            fn = "Helvetica-Bold"
            fs = 11 if bold else 9
            tc_val = C_GREEN if bold else C_DARK
            total_rows.append([
                Paragraph(label, ps(f"tl{label}", fontSize=fs, fontName=fn,
                                    textColor=C_DARK, alignment=TA_RIGHT)),
                Paragraph(value, ps(f"tv{label}", fontSize=fs, fontName=fn,
                                    textColor=tc_val, alignment=TA_RIGHT)),
            ])

        total_outer = Table(
            [[Spacer(1, 1), Table(total_rows, colWidths=[42*mm, 36*mm])]],
            colWidths=[W - 82*mm, 82*mm],
        )
        total_outer.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ]))
        story.append(total_outer)
        story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  PAYMENT RECEIVED BANNER
    # ══════════════════════════════════════════════════════════════════
    banner = Table(
        [[Paragraph(
            "&#10003;  PAYMENT RECEIVED",
            ps("paid", fontSize=11, fontName="Helvetica-Bold",
               textColor=C_GREEN, alignment=TA_CENTER),
        )]],
        colWidths=[W],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F0FFF6")),
        ("BOX",           (0, 0), (-1, -1), 1, colors.HexColor("#A8E6BF")),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(banner)
    story.append(Spacer(1, 8*mm))

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