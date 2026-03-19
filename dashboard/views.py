import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdminOrStaff


# ── HELPERS ────────────────────────────────────────────────────────────

HEADER_FILL   = PatternFill("solid", fgColor="1a1a2e")
HEADER_FONT   = Font(bold=True, color="FFFFFF", size=11)
HEADER_ALIGN  = Alignment(horizontal="center", vertical="center", wrap_text=True)

ALT_FILL      = PatternFill("solid", fgColor="F2F2F2")
BORDER_SIDE   = Side(style="thin", color="CCCCCC")
CELL_BORDER   = Border(
    left=BORDER_SIDE, right=BORDER_SIDE,
    top=BORDER_SIDE,  bottom=BORDER_SIDE,
)


def style_header_row(ws, headers):
    """Apply header styling to row 1."""
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font      = HEADER_FONT
        cell.fill      = HEADER_FILL
        cell.alignment = HEADER_ALIGN
        cell.border    = CELL_BORDER


def style_data_rows(ws, start_row, end_row, num_cols):
    """Apply alternating row colours and borders."""
    for row in range(start_row, end_row + 1):
        fill = ALT_FILL if row % 2 == 0 else None
        for col in range(1, num_cols + 1):
            cell = ws.cell(row=row, column=col)
            cell.border    = CELL_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if fill:
                cell.fill = fill


def auto_fit_columns(ws, headers):
    """Set column widths based on header length."""
    for col_num, header in enumerate(headers, 1):
        col_letter = get_column_letter(col_num)
        ws.column_dimensions[col_letter].width = max(len(header) + 4, 16)
    ws.row_dimensions[1].height = 30


def make_response(wb, filename):
    """Return Excel file as HTTP response."""
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


def fmt_dt(dt):
    """Format datetime nicely."""
    if not dt:
        return "—"
    return dt.strftime("%d %b %Y %H:%M")


def fmt_date(d):
    """Format date nicely."""
    if not d:
        return "—"
    return d.strftime("%d %b %Y")


# ── EXPORT ENQUIRIES ───────────────────────────────────────────────────

class ExportEnquiriesView(APIView):
    """
    GET /api/dashboard/export/enquiries/
    Admin/Staff — exports all enquiries to Excel.

    Optional filters:
      ?order_type=private_label | white_label | fabrics | others
      ?status=new | contacted | ...
      ?date_from=2026-01-01
      ?date_to=2026-03-31
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        from enquiries.models import Enquiry

        qs = Enquiry.objects.select_related(
            "assigned_to_user", "wl_prototype", "fabric", "customer"
        ).order_by("-created_at")

        # Apply filters
        order_type = request.query_params.get("order_type")
        status     = request.query_params.get("status")
        date_from  = request.query_params.get("date_from")
        date_to    = request.query_params.get("date_to")

        if order_type: qs = qs.filter(order_type=order_type)
        if status:     qs = qs.filter(status=status)
        if date_from:  qs = qs.filter(created_at__date__gte=date_from)
        if date_to:    qs = qs.filter(created_at__date__lte=date_to)

        wb = openpyxl.Workbook()

        # ── Sheet 1: All Enquiries ─────────────────────────────────── #
        ws = wb.active
        ws.title = "All Enquiries"

        headers = [
            "Enquiry No.", "Order Type", "Status", "Source Page",
            "Full Name", "Phone", "Email", "Brand Name",
            "Company Age (Yrs)", "Total Pieces Req.", "Annual Revenue",
            "Message",
            "WL Prototype Code", "Fabric Name",
            "Assigned To", "Is Viewed", "Viewed At",
            "Admin Notes", "Created At", "Updated At",
        ]

        style_header_row(ws, headers)

        for row_num, enq in enumerate(qs, start=2):
            ws.append([
                enq.enquiry_number,
                enq.get_order_type_display(),
                enq.get_status_display(),
                enq.get_source_page_display() if enq.source_page else "—",
                enq.full_name,
                enq.phone,
                enq.email,
                enq.brand_name,
                enq.company_age_years or "—",
                enq.total_pieces_required or "—",
                enq.annual_revenue or "—",
                enq.message,
                enq.wl_prototype.prototype_code if enq.wl_prototype else "—",
                enq.fabric.fabric_name if enq.fabric else "—",
                enq.assigned_to_user.email if enq.assigned_to_user else "—",
                "Yes" if enq.is_viewed else "No",
                fmt_dt(enq.viewed_at),
                enq.admin_notes or "—",
                fmt_dt(enq.created_at),
                fmt_dt(enq.updated_at),
            ])

        style_data_rows(ws, 2, qs.count() + 1, len(headers))
        auto_fit_columns(ws, headers)
        ws.freeze_panes = "A2"

        # ── Sheet 2: Summary by Order Type ────────────────────────── #
        ws2 = wb.create_sheet("Summary by Type")
        summary_headers = ["Order Type", "Total", "New", "Contacted",
                            "Prospect", "Accepted", "Rejected", "Closed"]
        style_header_row(ws2, summary_headers)

        order_types = ["private_label", "white_label", "fabrics", "others"]
        for i, ot in enumerate(order_types, start=2):
            subset = qs.filter(order_type=ot)
            ws2.append([
                ot.replace("_", " ").title(),
                subset.count(),
                subset.filter(status="new").count(),
                subset.filter(status="contacted").count(),
                subset.filter(status="prospect").count(),
                subset.filter(status="accepted").count(),
                subset.filter(status="rejected").count(),
                subset.filter(status="closed").count(),
            ])

        style_data_rows(ws2, 2, len(order_types) + 1, len(summary_headers))
        auto_fit_columns(ws2, summary_headers)

        filename = f"enquiries_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return make_response(wb, filename)


# ── EXPORT ORDERS ──────────────────────────────────────────────────────

class ExportOrdersView(APIView):
    """
    GET /api/dashboard/export/orders/
    Admin/Staff — exports all orders to Excel.

    Optional filters:
      ?order_type=private_label | white_label | fabrics
      ?status=order_placed | cutting | ...
      ?date_from=2026-01-01
      ?date_to=2026-03-31
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        from orders.models import Order

        qs = Order.objects.select_related(
            "customer_user", "created_by_user",
            "white_label_catalogue", "fabric_catalogue",
            "enquiry",
        ).order_by("-created_at")

        # Apply filters
        order_type = request.query_params.get("order_type")
        status     = request.query_params.get("status")
        date_from  = request.query_params.get("date_from")
        date_to    = request.query_params.get("date_to")

        if order_type: qs = qs.filter(order_type=order_type)
        if status:     qs = qs.filter(status=status)
        if date_from:  qs = qs.filter(created_at__date__gte=date_from)
        if date_to:    qs = qs.filter(created_at__date__lte=date_to)

        wb = openpyxl.Workbook()

        # ── Sheet 1: All Orders ────────────────────────────────────── #
        ws = wb.active
        ws.title = "All Orders"

        headers = [
            "Order No.", "Order Type", "Status",
            "Customer Email", "Created By",
            "WL Prototype", "Fabric",
            "Style Name", "Category", "Garment Type",
            "Fit Sizes", "Total Qty", "MOQ",
            "Customization Notes", "Message", "Fabric Type",
            "Payment Amount", "Admin Notes",
            "Enquiry No.", "Created At", "Updated At",
        ]

        style_header_row(ws, headers)

        for row_num, order in enumerate(qs, start=2):
            ws.append([
                order.order_number,
                order.get_order_type_display(),
                order.status.replace("_", " ").title(),
                order.customer_user.email,
                order.created_by_user.email,
                order.white_label_catalogue.prototype_code if order.white_label_catalogue else "—",
                order.fabric_catalogue.fabric_name if order.fabric_catalogue else "—",
                order.style_name or "—",
                order.for_category or "—",
                order.garment_type or "—",
                order.fit_sizes or "—",
                order.total_quantity,
                order.moq or "—",
                order.customization_notes or "—",
                order.message or "—",
                order.fabric_type or "—",
                f"₹{order.payment_amount}" if order.payment_amount else "—",
                order.notes or "—",
                order.enquiry.enquiry_number if order.enquiry else "—",
                fmt_dt(order.created_at),
                fmt_dt(order.updated_at),
            ])

        style_data_rows(ws, 2, qs.count() + 1, len(headers))
        auto_fit_columns(ws, headers)
        ws.freeze_panes = "A2"

        # ── Sheet 2: Summary by Order Type ────────────────────────── #
        ws2 = wb.create_sheet("Summary by Type")
        summary_headers = [
            "Order Type", "Total",
            "Order Placed", "In Progress", "Payment Pending",
            "Payment Done", "Dispatched", "Delivered",
        ]
        style_header_row(ws2, summary_headers)

        order_types = ["private_label", "white_label", "fabrics"]
        for ot in order_types:
            subset = qs.filter(order_type=ot)
            in_progress = subset.exclude(
                status__in=["order_placed", "payment_pending",
                            "payment_done", "dispatch", "delivered"]
            ).count()
            ws2.append([
                ot.replace("_", " ").title(),
                subset.count(),
                subset.filter(status="order_placed").count(),
                in_progress,
                subset.filter(status="payment_pending").count(),
                subset.filter(status="payment_done").count(),
                subset.filter(status="dispatch").count(),
                subset.filter(status="delivered").count(),
            ])

        style_data_rows(ws2, 2, len(order_types) + 1, len(summary_headers))
        auto_fit_columns(ws2, summary_headers)

        # ── Sheet 3: Stage History ─────────────────────────────────── #
        ws3 = wb.create_sheet("Stage History")
        history_headers = [
            "Order No.", "Order Type", "Stage",
            "Changed By", "Notes", "Changed At",
        ]
        style_header_row(ws3, history_headers)

        from orders.models import OrderStageHistory
        history_qs = OrderStageHistory.objects.select_related(
            "order", "changed_by"
        ).filter(order__in=qs).order_by("order__order_number", "changed_at")

        for row_num, h in enumerate(history_qs, start=2):
            ws3.append([
                h.order.order_number,
                h.order.get_order_type_display(),
                h.stage.replace("_", " ").title(),
                h.changed_by.email if h.changed_by else "System",
                h.notes or "—",
                fmt_dt(h.changed_at),
            ])

        style_data_rows(ws3, 2, history_qs.count() + 1, len(history_headers))
        auto_fit_columns(ws3, history_headers)

        filename = f"orders_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return make_response(wb, filename)


# ── DASHBOARD SUMMARY ──────────────────────────────────────────────────

class DashboardSummaryView(APIView):
    """
    GET /api/dashboard/summary/
    Admin/Staff — returns counts for dashboard widgets.
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        from enquiries.models import Enquiry
        from orders.models import Order

        return __import__('rest_framework').response.Response({
            "enquiries": {
                "total":         Enquiry.objects.count(),
                "unread":        Enquiry.objects.filter(is_viewed=False).count(),
                "new":           Enquiry.objects.filter(status="new").count(),
                "by_type": {
                    "private_label": Enquiry.objects.filter(order_type="private_label").count(),
                    "white_label":   Enquiry.objects.filter(order_type="white_label").count(),
                    "fabrics":       Enquiry.objects.filter(order_type="fabrics").count(),
                    "others":        Enquiry.objects.filter(order_type="others").count(),
                },
            },
            "orders": {
                "total":           Order.objects.count(),
                "order_placed":    Order.objects.filter(status="order_placed").count(),
                "in_progress":     Order.objects.exclude(
                    status__in=["order_placed","payment_pending",
                                "payment_done","dispatch","delivered"]
                ).count(),
                "payment_pending": Order.objects.filter(status="payment_pending").count(),
                "payment_done":    Order.objects.filter(status="payment_done").count(),
                "dispatched":      Order.objects.filter(status="dispatch").count(),
                "delivered":       Order.objects.filter(status="delivered").count(),
                "by_type": {
                    "private_label": Order.objects.filter(order_type="private_label").count(),
                    "white_label":   Order.objects.filter(order_type="white_label").count(),
                    "fabrics":       Order.objects.filter(order_type="fabrics").count(),
                },
            },
        })