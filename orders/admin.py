from django.contrib import admin
from django.utils.html import format_html
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
        "garment_type", "created_at",
    ]
    list_filter   = ["order_type", "status", "for_category", "fabric_type"]
    search_fields = ["order_number", "customer_user__email", "style_name"]
    ordering      = ["-created_at"]
    inlines       = [OrderStageHistoryInline, OrderImageInline]

    # ------------------------------------------------------------------ #
    # Admin can only:
    # 1. View all order details (read-only)
    # 2. Update status + notes
    # 3. Link enquiry (traceability)
    # Everything else was auto-filled when order was created
    # ------------------------------------------------------------------ #

    readonly_fields = [
        # Auto-filled at creation — never editable
        "id", "order_number", "order_type",
        "customer_user", "created_by_user",
        "white_label_catalogue", "fabric_catalogue",
        "pl_fabric_1", "pl_fabric_2", "pl_fabric_3",
        "for_category", "garment_type", "fabric_type",
        "fit_sizes", "size_breakdown",
        "total_quantity", "moq",
        "style_name",
        "message",
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
            "description": "Auto-filled from the catalogue item the customer selected.",
        }),
        ("Order Details", {
            "fields": (
                "style_name", "for_category", "garment_type",
                "fabric_type", "fit_sizes", "size_breakdown",
                "total_quantity", "moq",
            ),
            "description": "Auto-filled at the time of order placement.",
        }),
        ("Selected Fabrics (Private Label)", {
            "fields": ("pl_fabric_1", "pl_fabric_2", "pl_fabric_3"),
            "description": "Up to 3 fabrics selected by the customer for their Private Label order.",
        }),
        ("Customer Notes", {
            "fields": ("customization_notes", "message"),
            "description": "Entered by customer — customization_notes (WL) | message (Fabrics).",
        }),
        # ── Admin editable fields ──────────────────────────────────────
        ("Status", {
            "fields": ("status",),
            "description": "Update order stage here. Stage history is tracked automatically.",
        }),
        ("Traceability", {
            "fields": ("enquiry",),
            "description": "Link to the original enquiry that led to this order.",
        }),
        ("Admin Notes", {
            "fields": ("notes",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def save_model(self, request, obj, form, change):
        if change:
            # Track status change in history when admin updates from admin panel
            old = Order.objects.get(pk=obj.pk)
            if old.status != obj.status:
                OrderStageHistory.objects.create(
                    order      = obj,
                    stage      = obj.status,
                    changed_by = request.user,
                    notes      = "Updated via admin panel.",
                )
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # Orders are created by customers via API — not manually in admin
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
        # Timeline is immutable — no editing
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