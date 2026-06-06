# orders/models.py

import uuid
from django.core.validators import MaxValueValidator
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
    ("sample_request",           "Sample request"),
    ("sample_approval",          "Sample approval"),
    ("sample_rework",            "Sample Rework"),
    ("order_placed",             "Advance Pending"),
    ("advance_paid",             "Advance Paid"),
    ("bulk_production",          "Bulk production"),
    ("quality_inspection",       "Quality Inspection"),
    ("packing",                  "Packing"),
    ("payment_pending",          "Payment Pending"),
    ("payment_done",             "Payment Done"),
    ("dispatch",                 "Dispatch"),
    ("shipment_tracking",        "Shippment tracking details"),
    ("delivered",                "Delivered"),
]

WHITE_LABEL_STAGES = PRIVATE_LABEL_STAGES

# Fabrics — with swatch (when customer requests swatch before bulk)
FABRICS_STAGES_WITH_SWATCH = [
    ("swatch_sent",              "Swatch sent"),
    ("swatch_received",          "Swatch Received"),
    ("swatch_approved",          "Swatch Approved or Swatch Rework"),
    ("swatch_rework",            "Swatch Rework"),
    ("order_placed",             "Advance Pending"),
    ("advance_paid",             "Advance Paid"),
    ("bulk_production",          "Bulk production"),
    ("quality_inspection",       "Quality Inspection"),
    ("packing",                  "Packing"),
    ("payment_pending",          "Payment Pending"),
    ("payment_done",             "Payment Done"),
    ("dispatch",                 "Dispatch"),
    ("shipment_tracking",        "Shippment tracking details"),
    ("delivered",                "Delivered"),
]

# Fabrics — without swatch (direct bulk order)
FABRICS_STAGES_NO_SWATCH = [
    ("order_placed",             "Advance Pending"),
    ("advance_paid",             "Advance Paid"),
    ("bulk_production",          "Bulk production"),
    ("quality_inspection",       "Quality Inspection"),
    ("packing",                  "Packing"),
    ("payment_pending",          "Payment Pending"),
    ("payment_done",             "Payment Done"),
    ("dispatch",                 "Dispatch"),
    ("shipment_tracking",        "Shippment tracking details"),
    ("delivered",                "Delivered"),
]

# Combined for model field choices — include all possible stages
FABRICS_STAGES = FABRICS_STAGES_WITH_SWATCH  # superset for choices

ALL_STATUS_CHOICES = list({s[0]: s for s in
    PRIVATE_LABEL_STAGES + WHITE_LABEL_STAGES + FABRICS_STAGES + [
        ("sample_request", "Sample request"),
        ("sample_approval", "Sample approval"),
        ("sample_rework", "Sample Rework"),
        ("swatch_sent", "Swatch sent"),
        ("swatch_received", "Swatch Received"),
        ("swatch_approved", "Swatch Approved or Swatch Rework"),
        ("swatch_rework", "Swatch Rework"),
        ("bulk_production", "Bulk production"),
        ("quality_inspection", "Quality Inspection"),
        ("shipment_tracking", "Shippment tracking details"),
        ("advance_paid", "Advance Paid"),
    ]
}.values()) + [("cancelled", "Cancelled")]



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

    # Private Label — up to 3 fabric selections
    pl_fabric_1 = models.ForeignKey(
        "catalogue.FabricsCatalogue",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="pl_orders_fabric_1",
    )
    pl_fabric_2 = models.ForeignKey(
        "catalogue.FabricsCatalogue",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="pl_orders_fabric_2",
    )
    pl_fabric_3 = models.ForeignKey(
        "catalogue.FabricsCatalogue",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="pl_orders_fabric_3",
    )

    # PL & WL fields
    for_category = models.CharField(max_length=10, choices=ForCategory.choices,
                                     null=True, blank=True)
    garment_type = models.CharField(max_length=100, null=True, blank=True,
                                     help_text="Kurti / Frock / Maxi etc.")

    # Sizes
    fit_sizes = models.CharField(max_length=100, null=True, blank=True)
    size_breakdown = models.JSONField(
        null=True, blank=True,
        help_text='e.g. [{"size":"S","quantity":24},{"size":"M","quantity":24}]',
    )

    # Quantity
    total_quantity = models.IntegerField(help_text="Total qty required")
    moq            = models.IntegerField(null=True, blank=True,
                                          validators=[MaxValueValidator(9999)],
                                          help_text="MOQ snapshot at time of order")

    # WL specific
    customization_notes = models.TextField(null=True, blank=True)

    # Fabrics specific
    message      = models.TextField(null=True, blank=True,
                                     help_text="Fabrics order message")
    fabric_type  = models.CharField(max_length=10, choices=FabricType.choices,
                                     null=True, blank=True)

    # ── NEW: Swatch required for fabric orders ──────────────────────────
    swatch_required = models.BooleanField(
        default=False,
        help_text="Customer requested a fabric swatch before placing bulk order.",
    )

    # Status
    status = models.CharField(
        max_length=30,
        choices=ALL_STATUS_CHOICES,
        default="order_placed",
    )

    # Staff assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_orders",
        help_text="Staff member responsible for this order",
        limit_choices_to={"role__in": ["admin", "staff"]},
    )

    # Admin notes
    notes = models.TextField(null=True, blank=True,
                              help_text="Internal admin notes")

    # Payment amount
    payment_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
    )
    advance_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
    )

    # Invoice / GST fields
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text="Rate per unit (used for invoice GST calculation)",
    )
    hsn_code = models.CharField(
        max_length=20, blank=True, default="",
        help_text="HSN / SAC code for the item",
    )
    gst_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=5.00,
        help_text="Total GST % (split equally as CGST + SGST, e.g. 5 = 2.5+2.5)",
    )

    tracking_link = models.URLField(
        max_length=500, null=True, blank=True,
        help_text="Third-party shipment tracking webpage link"
    )
    tracking_code = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Shipment tracking code/number"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = "orders"
        ordering  = ["-created_at"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        indexes = [
            models.Index(fields=["order_type"],    name="idx_order_type"),
            models.Index(fields=["status"],        name="idx_order_status"),
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
        """
        Returns the ordered list of (value, label) stages for this order.
        Fabric orders return different stages depending on swatch_required.
        """
        if self.order_type == OrderType.PRIVATE_LABEL:
            return PRIVATE_LABEL_STAGES
        elif self.order_type == OrderType.WHITE_LABEL:
            return WHITE_LABEL_STAGES
        elif self.order_type == OrderType.FABRICS:
            if self.swatch_required:
                return FABRICS_STAGES_WITH_SWATCH
            return FABRICS_STAGES_NO_SWATCH
        return FABRICS_STAGES_NO_SWATCH

    @property
    def dynamic_stages(self):
        """
        Computes the sequence of stages dynamically based on OrderStageHistory.
        Handles swatch/sample rework cycles dynamically.
        Returns a list of dicts: [{'value': '...', 'label': '...', 'status': '...', 'date': '...', 'notes': '...'}]
        """
        base_stages = []
        if self.order_type == "fabrics":
            if self.swatch_required:
                base_stages = [
                    {"value": "swatch_sent", "label": "Swatch sent"},
                    {"value": "swatch_received", "label": "Swatch Received"},
                    {"value": "swatch_approved", "label": "Swatch Approved or Swatch Rework"},
                ]
            else:
                base_stages = []
        else: # white_label or private_label
            base_stages = [
                {"value": "sample_request", "label": "Sample request"},
                {"value": "sample_approval", "label": "Sample approval"},
            ]

        common_stages = [
            {"value": "order_placed", "label": "Advance Pending"},
            {"value": "advance_paid", "label": "Advance Paid"},
            {"value": "bulk_production", "label": "Bulk production"},
            {"value": "quality_inspection", "label": "Quality Inspection"},
            {"value": "packing", "label": "Packing"},
            {"value": "payment_pending", "label": "Payment Pending"},
            {"value": "payment_done", "label": "Payment Done"},
            {"value": "dispatch", "label": "Dispatch"},
            {"value": "shipment_tracking", "label": "Shippment tracking details"},
            {"value": "delivered", "label": "Delivered"},
        ]

        # Use prefetchable stage_history
        history = list(self.stage_history.all().order_by("changed_at"))

        swatch_rework_count = sum(1 for h in history if h.stage == "swatch_rework")
        sample_rework_count = sum(1 for h in history if h.stage == "sample_rework")

        stages = []
        if self.order_type == "fabrics" and self.swatch_required:
            for _ in range(swatch_rework_count):
                stages.extend([
                    {"value": "swatch_sent", "label": "Swatch sent"},
                    {"value": "swatch_received", "label": "Swatch Received"},
                    {"value": "swatch_rework", "label": "Swatch Rework"},
                ])
            stages.extend([
                {"value": "swatch_sent", "label": "Swatch sent"},
                {"value": "swatch_received", "label": "Swatch Received"},
                {"value": "swatch_approved", "label": "Swatch Approved or Swatch Rework"},
            ])
        elif self.order_type in ["white_label", "private_label"]:
            for _ in range(sample_rework_count):
                stages.extend([
                    {"value": "sample_request", "label": "Sample request"},
                    {"value": "sample_rework", "label": "Sample Rework"},
                ])
            stages.extend([
                {"value": "sample_request", "label": "Sample request"},
                {"value": "sample_approval", "label": "Sample approval"},
            ])

        stages.extend(common_stages)

        for s in stages:
            s["status"] = "pending"
            s["date"] = None
            s["notes"] = None

        def stages_match(h_stage, ds_value):
            if h_stage == ds_value:
                return True
            if h_stage == "swatch_approved" and ds_value == "swatch_approved":
                return True
            if h_stage == "swatch_rework" and ds_value == "swatch_rework":
                return True
            if h_stage == "sample_approved" and ds_value == "sample_approval":
                return True
            if h_stage == "sample_rework" and ds_value == "sample_rework":
                return True
            return False

        ds_idx = 0
        num_ds = len(stages)

        for h in history:
            idx = ds_idx
            while idx < num_ds:
                if stages_match(h.stage, stages[idx]["value"]):
                    for j in range(ds_idx, idx):
                        stages[j]["status"] = "completed"
                    
                    stages[idx]["status"] = "completed"
                    stages[idx]["date"] = h.changed_at.isoformat()
                    stages[idx]["notes"] = h.notes

                    if h.stage == "swatch_approved":
                        stages[idx]["label"] = "Swatch Approved"
                    elif h.stage == "swatch_rework":
                        stages[idx]["label"] = "Swatch Rework"
                    elif h.stage == "sample_approved":
                        stages[idx]["label"] = "Sample Approved"
                    elif h.stage == "sample_rework":
                        stages[idx]["label"] = "Sample Rework"

                    ds_idx = idx + 1
                    break
                idx += 1

        current_status = self.status
        mapped_current = current_status
        if current_status == "swatch_approved" or current_status == "swatch_rework":
            mapped_current = "swatch_approved" if current_status == "swatch_approved" else "swatch_rework"
        elif current_status == "sample_approved" or current_status == "sample_rework":
            mapped_current = "sample_approval" if current_status == "sample_approved" else "sample_rework"

        current_idx = -1
        for i, s in enumerate(stages):
            if s["value"] == mapped_current or (mapped_current == "swatch_approved" and s["value"] == "swatch_approved") or (mapped_current == "sample_approval" and s["value"] == "sample_approval"):
                current_idx = i
                if s["status"] != "completed":
                    break

        if current_idx != -1:
            stages[current_idx]["status"] = "current"
            for j in range(current_idx + 1, num_ds):
                stages[j]["status"] = "pending"
                stages[j]["date"] = None
                stages[j]["notes"] = None

        return stages



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
    notes      = models.TextField(null=True, blank=True)
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
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="order_notes")
    note       = models.TextField(help_text="Note content")
    added_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="order_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = "order_notes"
        ordering     = ["-created_at"]
        verbose_name = "Order Note"
        verbose_name_plural = "Order Notes"

    def __str__(self):
        return f"Note on {self.order.order_number}"