import uuid
from django.db import models
from django.conf import settings


class OrderType(models.TextChoices):
    PRIVATE_LABEL = "private_label", "Private Label"
    WHITE_LABEL   = "white_label",   "White Label"
    FABRICS       = "fabrics",       "Fabrics"


class ForCategory(models.TextChoices):
    WOMEN = "women", "Women"
    MEN   = "men",   "Men"
    KIDS  = "kids",  "Kids"


class FabricType(models.TextChoices):
    REGULAR = "regular", "Regular"
    NEW     = "new",     "New"
    STOCK   = "stock",   "Stock"


# ── ORDER STATUS PER TYPE ──────────────────────────────────────────────

PRIVATE_LABEL_STAGES = [
    ("order_placed",             "Order Placed"),
    ("sampling_fabric",          "Sampling Fabric"),
    ("sampling_style",           "Sampling Style"),
    ("sampling_fit",             "Sampling Fit"),
    ("sample_approval",          "Sample Approval"),
    ("sample_rework",            "Sample Rework"),
    ("sample_approved",          "Sample Approved"),
    ("fabric_procurement",       "Fabric Procurement / Production"),
    ("cutting",                  "Cutting"),
    ("production",               "Production"),
    ("packing",                  "Packing"),
    ("payment_pending",          "Payment Pending"),
    ("payment_done",             "Payment Done"),
    ("dispatch",                 "Dispatch"),
    ("delivered",                "Delivered"),
]

WHITE_LABEL_STAGES = [
    ("order_placed",    "Order Placed"),
    ("cutting",         "Cutting"),
    ("production",      "Production"),
    ("packing",         "Packing"),
    ("payment_pending", "Payment Pending"),
    ("payment_done",    "Payment Done"),
    ("dispatch",        "Dispatch"),
    ("delivered",       "Delivered"),
]

FABRICS_STAGES = [
    ("order_placed",    "Order Placed"),
    ("production",      "Production"),
    ("procurement",     "Procurement"),
    ("cutting",         "Cutting"),
    ("packing",         "Packing"),
    ("payment_pending", "Payment Pending"),
    ("payment_done",    "Payment Done"),
    ("dispatch",        "Dispatch"),
    ("delivered",       "Delivered"),
]

# Combined for model field choices
ALL_STATUS_CHOICES = list({s[0]: s for s in
    PRIVATE_LABEL_STAGES + WHITE_LABEL_STAGES + FABRICS_STAGES
}.values())


# ── ORDER ──────────────────────────────────────────────────────────────

class Order(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, blank=True,
                                    help_text="Auto-generated e.g. WL-2026-00001")
    order_type   = models.CharField(max_length=20, choices=OrderType.choices)

    # Who
    customer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        help_text="Customer who placed the order",
    )
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_orders",
        help_text="Admin or customer who created the order",
    )

    # Traceability — original enquiry
    enquiry = models.ForeignKey(
        "enquiries.Enquiry",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
        help_text="Original enquiry that led to this order",
    )

    # Catalogue references
    white_label_catalogue = models.ForeignKey(
        "catalogue.WLPrototype",
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="orders",
        help_text="Linked WL prototype — WL orders only",
    )
    fabric_catalogue = models.ForeignKey(
        "catalogue.FabricsCatalogue",
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="orders",
        help_text="Linked fabric — Fabrics orders only",
    )

    # Private Label fields
    style_name = models.CharField(max_length=200, null=True, blank=True,
                                   help_text="Private Label only")

    # Private Label — up to 3 fabric selections from fabrics catalogue
    pl_fabric_1 = models.ForeignKey(
        "catalogue.FabricsCatalogue",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="pl_orders_fabric_1",
        help_text="PL fabric choice 1",
    )
    pl_fabric_2 = models.ForeignKey(
        "catalogue.FabricsCatalogue",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="pl_orders_fabric_2",
        help_text="PL fabric choice 2",
    )
    pl_fabric_3 = models.ForeignKey(
        "catalogue.FabricsCatalogue",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="pl_orders_fabric_3",
        help_text="PL fabric choice 3",
    )

    # PL & WL fields
    for_category = models.CharField(max_length=10, choices=ForCategory.choices,
                                     null=True, blank=True)
    garment_type = models.CharField(max_length=100, null=True, blank=True,
                                     help_text="Kurti / Frock / Maxi etc.")

    # Sizes
    fit_sizes = models.CharField(max_length=100, null=True, blank=True,
                                  help_text="Selected size names e.g. S,M,L,XL")
    size_breakdown = models.JSONField(
        null=True, blank=True,
        help_text='e.g. [{"size":"S","quantity":24},{"size":"M","quantity":24}]',
    )

    # Quantity
    total_quantity = models.IntegerField(help_text="Total qty required")
    moq            = models.IntegerField(null=True, blank=True,
                                          help_text="MOQ snapshot at time of order")

    # WL specific
    customization_notes = models.TextField(null=True, blank=True,
                                            help_text="White Label customisation notes")

    # Fabrics specific
    message      = models.TextField(null=True, blank=True,
                                     help_text="Fabrics order message")
    fabric_type  = models.CharField(max_length=10, choices=FabricType.choices,
                                     null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=30,
        choices=ALL_STATUS_CHOICES,
        default="order_placed",
    )

    # Admin notes
    notes = models.TextField(null=True, blank=True,
                              help_text="Internal admin notes")

    # Payment amount — set by admin before moving to payment_pending
    payment_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text="Set this before changing status to payment_pending. "
                  "Razorpay payment will be auto-created on save.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = "orders"
        ordering  = ["-created_at"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        indexes = [
            models.Index(fields=["order_type"], name="idx_order_type"),
            models.Index(fields=["status"],     name="idx_order_status"),
            models.Index(fields=["customer_user"], name="idx_order_customer"),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            from django.utils import timezone
            year   = timezone.now().year
            prefix = {
                "private_label": "PL",
                "white_label":   "WL",
                "fabrics":       "FB",
            }.get(self.order_type, "ORD")
            count = Order.objects.filter(
                created_at__year=year,
                order_type=self.order_type,
            ).count() + 1
            self.order_number = f"{prefix}-{year}-{count:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_number} — {self.customer_user.email}"

    @property
    def valid_stages(self):
        """Returns the valid stages for this order type."""
        if self.order_type == OrderType.PRIVATE_LABEL:
            return PRIVATE_LABEL_STAGES
        elif self.order_type == OrderType.WHITE_LABEL:
            return WHITE_LABEL_STAGES
        return FABRICS_STAGES


# ── ORDER STAGE HISTORY ────────────────────────────────────────────────

class OrderStageHistory(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order      = models.ForeignKey(Order, on_delete=models.CASCADE,
                                    related_name="stage_history")
    stage      = models.CharField(max_length=30, choices=ALL_STATUS_CHOICES)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="order_stage_changes",
    )
    notes      = models.TextField(null=True, blank=True,
                                   help_text="Optional note for this stage")
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_stage_history"
        ordering = ["changed_at"]
        verbose_name = "Order Stage"
        verbose_name_plural = "Order Stage History"

    def __str__(self):
        return f"{self.order.order_number} → {self.stage} at {self.changed_at:%Y-%m-%d %H:%M}"


# ── ORDER IMAGES ───────────────────────────────────────────────────────

class OrderImage(models.Model):
    id    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE,
                               related_name="images")

    image       = models.ImageField(upload_to="orders/images/", null=True, blank=True)
    file_name   = models.CharField(max_length=200)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_images"
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"{self.file_name} — {self.order.order_number}"
    
# ── ORDER NOTES ────────────────────────────────────────────────────────
 
class OrderNote(models.Model):
    id    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="order_notes")
    note     = models.TextField(help_text="Note content")
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL,null=True, blank=True,on_delete=models.SET_NULL,related_name="order_notes",help_text="User who added the note",)
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table     = "order_notes"
        ordering     = ["-created_at"]
        verbose_name = "Order Note"
        verbose_name_plural = "Order Notes"
 
    def __str__(self):
        return f"Note on {self.order.order_number}"