import uuid
from django.db import models


class FitSizesField(models.TextField):
    """
    Stores fit sizes as a comma-separated string in the DB (SQLite compatible).
    Returns a Python list when accessed. Accepts a list when setting.
    """
    def from_db_value(self, value, expression, connection):
        return self._parse(value)

    def to_python(self, value):
        if isinstance(value, list):
            return value
        return self._parse(value)

    def get_prep_value(self, value):
        if isinstance(value, list):
            return ",".join(str(s).strip() for s in value if s)
        return value or ""

    def _parse(self, value):
        if not value:
            return []
        return [s.strip() for s in value.split(",") if s.strip()]


class GenderChoice(models.TextChoices):
    WOMEN = "women", "Women"
    MEN   = "men",   "Men"
    KIDS  = "kids",  "Kids"


class WLPrototype(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identity
    prototype_code  = models.CharField(max_length=30, unique=True, help_text="e.g. WL-2025-DW01")
    collection_name = models.CharField(max_length=150, null=True, blank=True)

    # Classification
    for_gender   = models.CharField(max_length=10, choices=GenderChoice.choices)
    garment_type = models.CharField(max_length=80, help_text="Kurti / Frock / Maxi / Pant etc.")

    # Media — actual file upload
    thumbnail = models.ImageField(
        upload_to="catalogue/thumbnails/",
        null=True,
        blank=True,
        help_text="Primary display image (upload from admin)",
    )

    # Order details
    moq = models.SmallIntegerField(default=15, help_text="Minimum order quantity (pcs/style)")

    # Sizing & customisation
    fit_sizes               = FitSizesField(null=True, blank=True, help_text="e.g. S,M,L,XL,XXL")
    customization_available = models.TextField(null=True, blank=True)

    # Pre-booking
    is_prebooking         = models.BooleanField(default=False)
    prebooking_close_date = models.DateField(null=True, blank=True)

    # Status & audit
    is_active        = models.BooleanField(default=True)
    created_by_admin = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="created_prototypes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wl_prototypes"
        ordering = ["-created_at"]
        verbose_name = "WL Prototype"
        verbose_name_plural = "WL Prototypes"
        indexes = [
            models.Index(fields=["prototype_code"], name="idx_prototype_code"),
            models.Index(fields=["for_gender"],     name="idx_prototype_gender"),
            models.Index(fields=["garment_type"],   name="idx_prototype_garment"),
            models.Index(fields=["is_active"],      name="idx_prototype_active"),
        ]

    def __str__(self):
        return f"{self.prototype_code} — {self.garment_type} ({self.for_gender})"


class WLPrototypeImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    prototype = models.ForeignKey(
        WLPrototype,
        on_delete=models.CASCADE,
        related_name="images",
    )

    # Actual file upload
    image = models.ImageField(
        upload_to="catalogue/images/",
        null=True,
        blank=True,
        help_text="Gallery image (upload from admin)",
    )
    sort_order  = models.SmallIntegerField(default=0, help_text="Display order in gallery")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "wl_prototype_images"
        ordering = ["sort_order", "uploaded_at"]
        verbose_name = "Prototype Image"
        verbose_name_plural = "Prototype Images"

    def __str__(self):
        return f"Image #{self.sort_order} — {self.prototype.prototype_code}"