import uuid
from django.db import models


class FitSizesField(models.TextField):
    """
    Stores fit sizes as a comma-separated string in the DB (SQLite compatible).
    Returns a Python list when accessed on the model instance.
    Accepts a list when setting e.g. prototype.fit_sizes = ['S','M','L','XL']
    """

    def from_db_value(self, value, expression, connection): return self._parse(value)

    def to_python(self, value):
        if isinstance(value, list): return value
        return self._parse(value)

    def get_prep_value(self, value):
        if isinstance(value, list): return ",".join(str(s).strip() for s in value if s)
        return value or ""

    def _parse(self, value):
        if not value: return []
        return [s.strip() for s in value.split(",") if s.strip()]


class GenderChoice(models.TextChoices):
    WOMEN = "women", "Women"
    MEN = "men", "Men"
    KIDS = "kids", "Kids"


class WLPrototype(models.Model):

    # Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identity
    prototype_code = models.CharField(max_length=30, unique=True, help_text="Admin-assigned code e.g. WL-2028-DW01")
    collection_name = models.CharField(max_length=150, null=True, blank=True, help_text="e.g. Diwali 2025, Christmas Collection")

    # Classification
    for_gender = models.CharField(max_length=10, choices=GenderChoice.choices, help_text="'women' | 'men' | 'kids'")
    garment_type = models.CharField(max_length=80, help_text="Kurti / Frock / Maxi / Pant etc.")

    # Media
    thumbnail_storage_path = models.TextField(null=True, blank=True, help_text="Primary display image path")

    # Order details
    moq = models.SmallIntegerField(default=15, help_text="Minimum order quantity (pcs/style)")

    # Sizing & customisation
    fit_sizes = FitSizesField(null=True, blank=True, help_text="List of sizes e.g. ['S','M','L','XL','XXL'] — stored as comma-separated string")
    customization_available = models.TextField(null=True, blank=True, help_text="Free-text customisation notes")

    # Pre-booking
    is_prebooking = models.BooleanField(default=False, help_text="true = Pre-booking prototype")
    prebooking_close_date = models.DateField(null=True, blank=True, help_text="Only relevant when is_prebooking = true")

    # Status & audit
    is_active = models.BooleanField(default=True, help_text="Soft-delete for catalogue management")
    created_by_admin = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_prototypes", help_text="Admin who created this prototype")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wl_prototypes"
        ordering = ["-created_at"]
        verbose_name = "WL Prototype"
        verbose_name_plural = "WL Prototypes"
        indexes = [
            models.Index(fields=["prototype_code"], name="idx_prototype_code"),
            models.Index(fields=["for_gender"], name="idx_prototype_gender"),
            models.Index(fields=["garment_type"], name="idx_prototype_garment"),
            models.Index(fields=["is_active"], name="idx_prototype_active"),
        ]

    def __str__(self):
        return f"{self.prototype_code} — {self.garment_type} ({self.for_gender})"


class WLPrototypeImage(models.Model):

    # Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Relation
    prototype = models.ForeignKey(WLPrototype, on_delete=models.CASCADE, related_name="images", help_text="Parent prototype")
    # Image
    storage_path = models.TextField(help_text="File path / URL of the gallery image")
    sort_order = models.SmallIntegerField(default=0, help_text="Controls image display order in gallery")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "wl_prototype_images"
        ordering = ["sort_order", "uploaded_at"]
        verbose_name = "Prototype Image"
        verbose_name_plural = "Prototype Images"

    def __str__(self):
        return f"Image #{self.sort_order} for {self.prototype.prototype_code}"