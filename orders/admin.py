from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.utils.safestring import mark_safe
from .models import Order, OrderStageHistory, OrderImage


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
    inlines       = [OrderStageHistoryInline, OrderImageInline]

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

            # Auto-create Razorpay payment when status → payment_pending
            # and payment_amount is set
            if (
                old.status != "payment_pending"
                and obj.status == "payment_pending"
                and obj.payment_amount
            ):
                self._create_razorpay_payment(request, obj)

        super().save_model(request, obj, form, change)

    def _create_razorpay_payment(self, request, order):
        """Auto-create Razorpay payment when admin sets payment_pending."""
        try:
            from payments import gateway
            from payments.models import PaymentTransaction, PaymentStatus
            from django.contrib.contenttypes.models import ContentType

            ct = ContentType.objects.get_for_model(order)

            # Don't create duplicate
            if PaymentTransaction.objects.filter(
                content_type=ct,
                object_id=order.id,
                status=PaymentStatus.PENDING,
            ).exists():
                messages.warning(request, "A pending payment already exists for this order.")
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
                f"✅ Razorpay payment created. Order ID: {result['razorpay_order_id']} "
                f"| Amount: ₹{order.payment_amount}"
            )
        except Exception as e:
            messages.error(request, f"❌ Failed to create Razorpay payment: {str(e)}")

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