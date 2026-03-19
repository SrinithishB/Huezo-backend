import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.http import HttpResponse
from django.contrib import messages
from .models import Order, OrderStageHistory, OrderImage, OrderNote


# ── EXCEL HELPER ───────────────────────────────────────────────────────

def export_orders_to_excel(queryset, filename):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"

    header_fill = PatternFill("solid", fgColor="1a1a2e")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border_side = Side(style="thin", color="CCCCCC")
    cell_border = Border(
        left=border_side, right=border_side,
        top=border_side,  bottom=border_side,
    )
    alt_fill = PatternFill("solid", fgColor="F2F2F2")

    headers = [
        "Order No.", "Order Type", "Status",
        "Customer Email", "Created By",
        "WL Prototype", "Fabric",
        "Style Name", "Category", "Garment Type",
        "Fit Sizes", "Total Qty", "MOQ",
        "Payment Amount", "Customization Notes",
        "Message", "Fabric Type",
        "Admin Notes", "Enquiry No.", "Created At",
    ]

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border    = cell_border
    ws.row_dimensions[1].height = 28

    for row_num, order in enumerate(queryset, start=2):
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
            f"₹{order.payment_amount}" if order.payment_amount else "—",
            order.customization_notes or "—",
            order.message or "—",
            order.fabric_type or "—",
            order.notes or "—",
            order.enquiry.enquiry_number if order.enquiry else "—",
            order.created_at.strftime("%d %b %Y %H:%M"),
        ])
        if row_num % 2 == 0:
            for col in range(1, len(headers) + 1):
                ws.cell(row=row_num, column=col).fill = alt_fill
        for col in range(1, len(headers) + 1):
            ws.cell(row=row_num, column=col).border = cell_border

    for col, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(col)].width = max(len(h) + 4, 16)
    ws.freeze_panes = "A2"

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


class OrderNoteInline(admin.TabularInline):
    model           = OrderNote
    extra           = 1
    fields          = ["note", "added_by", "created_at"]
    readonly_fields = ["added_by", "created_at"]
    ordering        = ["-created_at"]
    verbose_name    = "Note"
    verbose_name_plural = "Notes"

    def save_model(self, request, obj, form, change):
        if not obj.added_by:
            obj.added_by = request.user
        super().save_model(request, obj, form, change)


class OrderStageHistoryInline(admin.TabularInline):
    model           = OrderStageHistory
    extra           = 0
    readonly_fields = ["stage", "changed_by", "notes", "changed_at"]
    ordering        = ["changed_at"]
    can_delete      = False

    def has_add_permission(self, request, obj=None):
        return False


class OrderImageInline(admin.TabularInline):
    model           = OrderImage
    extra           = 0
    readonly_fields = ["image_preview", "file_name", "uploaded_at"]
    fields          = ["image", "image_preview", "file_name", "uploaded_at"]

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px;width:80px;object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"
    image_preview.short_description = "Preview"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = [
        "order_number", "order_type", "customer_user",
        "status", "total_quantity", "for_category",
        "garment_type", "payment_status_display", "created_at",
    ]
    list_filter   = ["order_type", "status", "for_category", "fabric_type"]
    search_fields = ["order_number", "customer_user__email", "style_name"]
    ordering      = ["-created_at"]
    inlines       = [OrderNoteInline, OrderStageHistoryInline, OrderImageInline]
    actions       = [
        "export_all_as_excel",
        "export_wl_as_excel",
        "export_pl_as_excel",
        "export_fabrics_as_excel",
        "mark_as_payment_pending",
        "mark_as_payment_done",
        "mark_as_dispatch",
        "mark_as_delivered",
    ]

    readonly_fields = [
        # Auto-filled at creation — never editable
        "id", "order_number", "order_type",
        "customer_user", "created_by_user",
        "white_label_catalogue", "fabric_catalogue",
        "pl_fabric_1", "pl_fabric_2", "pl_fabric_3",
        "for_category", "garment_type", "fabric_type",
        "fit_sizes", "size_breakdown",
        "total_quantity", "moq",
        "style_name", "message",
        # Payment — read only display
        "payment_info",
        "created_at", "updated_at",
    ]

    fieldsets = (
        ("Order Info", {
            "fields": ("id", "order_number", "order_type"),
        }),
        ("Parties", {
            "fields": ("customer_user", "created_by_user"),
            "description": "Auto-filled from the logged-in user who placed the order.",
        }),
        ("Catalogue Reference", {
            "fields": ("white_label_catalogue", "fabric_catalogue"),
        }),
        ("Order Details", {
            "fields": (
                "style_name", "for_category", "garment_type",
                "fabric_type", "fit_sizes", "size_breakdown",
                "total_quantity", "moq",
            ),
            "description": "Auto-filled at order placement.",
        }),
        ("Selected Fabrics (Private Label)", {
            "fields": ("pl_fabric_1", "pl_fabric_2", "pl_fabric_3"),
        }),
        ("Customer Notes", {
            "fields": ("customization_notes", "message"),
        }),
        # ── Admin editable ─────────────────────────────────────────── #
        ("Status", {
            "fields": ("status",),
            "description": "Update order stage here. Stage history is tracked automatically.",
        }),
        ("Payment", {
            "fields": ("payment_amount", "payment_info"),
            "description": (
                "Set the payment amount and save. "
                "When status is set to payment_pending, "
                "a Razorpay payment link will be auto-created for the customer."
            ),
        }),
        ("Traceability", {
            "fields": ("enquiry",),
        }),
        ("Admin Notes", {
            "fields": ("notes",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    # ── Custom display fields ──────────────────────────────────────── #

    def payment_status_display(self, obj):
        from payments.models import PaymentTransaction, PaymentStatus
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(obj)
        tx = PaymentTransaction.objects.filter(
            content_type=ct, object_id=obj.id
        ).order_by("-created_at").first()

        if not tx:
            return mark_safe('<span style="color:#999;">—</span>')

        colors = {
            "pending":  "#f0a500",
            "paid":     "#27ae60",
            "failed":   "#e74c3c",
            "refunded": "#8e44ad",
        }
        color = colors.get(tx.status, "#999")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color, tx.get_status_display()
        )
    payment_status_display.short_description = "Payment"

    def payment_info(self, obj):
        from payments.models import PaymentTransaction
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(obj)
        tx = PaymentTransaction.objects.filter(
            content_type=ct, object_id=obj.id
        ).order_by("-created_at").first()

        if not tx:
            return mark_safe('<span style="color:#999;">No payment created yet.</span>')

        color_map = {
            "pending":  "#f0a500",
            "paid":     "#27ae60",
            "failed":   "#e74c3c",
            "refunded": "#8e44ad",
        }
        color = color_map.get(tx.status, "#999")

        html = f"""
        <table style="border-collapse:collapse;font-size:13px;">
          <tr><td style="padding:3px 10px 3px 0;color:#666;">Status</td>
              <td style="color:{color};font-weight:600;">{tx.get_status_display()}</td></tr>
          <tr><td style="padding:3px 10px 3px 0;color:#666;">Amount</td>
              <td>₹{tx.amount} {tx.currency}</td></tr>
          <tr><td style="padding:3px 10px 3px 0;color:#666;">Razorpay Order ID</td>
              <td>{tx.razorpay_order_id or '—'}</td></tr>
          <tr><td style="padding:3px 10px 3px 0;color:#666;">Payment Reference</td>
              <td>{tx.payment_reference or '—'}</td></tr>
          <tr><td style="padding:3px 10px 3px 0;color:#666;">Paid At</td>
              <td>{tx.paid_at.strftime('%d %b %Y %H:%M') if tx.paid_at else '—'}</td></tr>
        </table>
        """
        return mark_safe(html)
    payment_info.short_description = "Payment Details"

    # ── Save logic ─────────────────────────────────────────────────── #

    # ── Actions ────────────────────────────────────────────────────── #

    @admin.action(description="📥 Export selected orders to Excel")
    def export_all_as_excel(self, request, queryset):
        qs = queryset.select_related(
            "customer_user", "created_by_user",
            "white_label_catalogue", "fabric_catalogue", "enquiry",
        )
        return export_orders_to_excel(qs, f"orders_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

    @admin.action(description="📥 Export White Label orders to Excel")
    def export_wl_as_excel(self, request, queryset):
        qs = queryset.filter(order_type="white_label").select_related(
            "customer_user", "created_by_user", "white_label_catalogue", "enquiry",
        )
        return export_orders_to_excel(qs, f"orders_wl_{timezone.now().strftime('%Y%m%d')}.xlsx")

    @admin.action(description="📥 Export Private Label orders to Excel")
    def export_pl_as_excel(self, request, queryset):
        qs = queryset.filter(order_type="private_label").select_related(
            "customer_user", "created_by_user", "enquiry",
        )
        return export_orders_to_excel(qs, f"orders_pl_{timezone.now().strftime('%Y%m%d')}.xlsx")

    @admin.action(description="📥 Export Fabrics orders to Excel")
    def export_fabrics_as_excel(self, request, queryset):
        qs = queryset.filter(order_type="fabrics").select_related(
            "customer_user", "created_by_user", "fabric_catalogue", "enquiry",
        )
        return export_orders_to_excel(qs, f"orders_fabrics_{timezone.now().strftime('%Y%m%d')}.xlsx")

    @admin.action(description="💳 Mark selected orders as Payment Pending")
    def mark_as_payment_pending(self, request, queryset):
        self._bulk_update_status(request, queryset, "payment_pending")

    @admin.action(description="✅ Mark selected orders as Payment Done")
    def mark_as_payment_done(self, request, queryset):
        self._bulk_update_status(request, queryset, "payment_done")

    @admin.action(description="🚚 Mark selected orders as Dispatched")
    def mark_as_dispatch(self, request, queryset):
        self._bulk_update_status(request, queryset, "dispatch")

    @admin.action(description="📦 Mark selected orders as Delivered")
    def mark_as_delivered(self, request, queryset):
        self._bulk_update_status(request, queryset, "delivered")

    def _bulk_update_status(self, request, queryset, new_status):
        from .models import OrderStageHistory
        updated = 0
        for order in queryset:
            if order.status != new_status:
                order.status = new_status
                order.save(update_fields=["status", "updated_at"])
                OrderStageHistory.objects.create(
                    order      = order,
                    stage      = new_status,
                    changed_by = request.user,
                    notes      = f"Bulk updated via admin panel.",
                )
                updated += 1
        self.message_user(
            request,
            f"{updated} order(s) updated to '{new_status.replace('_', ' ').title()}'."
        )

    def save_model(self, request, obj, form, change):
        if change:
            old = Order.objects.get(pk=obj.pk)

            # Track status change
            if old.status != obj.status:
                OrderStageHistory.objects.create(
                    order      = obj,
                    stage      = obj.status,
                    changed_by = request.user,
                    notes      = "Updated via admin panel.",
                )

            # Auto-create Razorpay payment when:
            # 1. Status just changed to payment_pending, OR
            # 2. Amount was just set while already at payment_pending
            status_just_changed = (old.status != "payment_pending" and obj.status == "payment_pending")
            amount_just_set     = (obj.status == "payment_pending" and obj.payment_amount and not old.payment_amount)

            if (status_just_changed or amount_just_set) and obj.payment_amount:
                self._create_razorpay_payment(request, obj)

        super().save_model(request, obj, form, change)

    def _create_razorpay_payment(self, request, order):
        """Auto-create Razorpay payment when admin sets payment_pending."""
        import traceback
        try:
            from payments import gateway
            from payments.models import PaymentTransaction, PaymentStatus
            from django.contrib.contenttypes.models import ContentType

            # Debug info
            messages.info(request, f"🔄 Creating payment for {order.order_number} | Amount: ₹{order.payment_amount}")

            ct = ContentType.objects.get_for_model(order)

            # Don't create duplicate
            existing = PaymentTransaction.objects.filter(
                content_type=ct,
                object_id=order.id,
                status=PaymentStatus.PENDING,
            )
            if existing.exists():
                messages.warning(request, f"⚠️ Pending payment already exists: {existing.first().razorpay_order_id}")
                return

            result = gateway.create_payment(
                content_object = order,
                amount         = order.payment_amount,
                payment_type   = "order",
                paid_by        = order.customer_user,
                notes          = f"Payment for {order.order_number}",
            )
            messages.success(
                request,
                f"✅ Razorpay payment created. Order ID: {result['razorpay_order_id']} | Amount: ₹{order.payment_amount}"
            )
        except Exception as e:
            messages.error(request, f"❌ Payment error: {str(e)}")
            messages.error(request, f"🔍 Traceback: {traceback.format_exc()[:600]}")

    def has_add_permission(self, request):
        return False


@admin.register(OrderStageHistory)
class OrderStageHistoryAdmin(admin.ModelAdmin):
    list_display    = ["order", "stage", "changed_by", "notes", "changed_at"]
    list_filter     = ["stage"]
    search_fields   = ["order__order_number"]
    readonly_fields = ["id", "order", "stage", "changed_by", "changed_at"]
    ordering        = ["-changed_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OrderImage)
class OrderImageAdmin(admin.ModelAdmin):
    list_display    = ["file_name", "order", "image_preview", "uploaded_at"]
    search_fields   = ["file_name", "order__order_number"]
    readonly_fields = ["id", "image_preview", "order", "file_name", "uploaded_at"]
    ordering        = ["-uploaded_at"]

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px;width:80px;object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"
    image_preview.short_description = "Preview"

    def has_add_permission(self, request):
        return False