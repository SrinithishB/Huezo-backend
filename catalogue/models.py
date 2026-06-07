import uuid
import ast
from django.core.validators import MaxValueValidator
from django.db import models
from django import forms


class FitSizesFormField(forms.CharField):
    def to_python(self, value):
        if not value:
            return []
        value = value.strip()
        if value.startswith('[') and value.endswith(']'):
            try:
                parsed = ast.literal_eval(value)
                if isinstance(parsed, list):
                    return [str(s).replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip() for s in parsed if s]
            except Exception:
                pass
        return [str(s).replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip() for s in value.split(',') if s.strip()]

    def prepare_value(self, value):
        if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
            try:
                parsed = ast.literal_eval(value)
                if isinstance(parsed, list):
                    value = parsed
            except Exception:
                pass
        if isinstance(value, list):
            return ", ".join(value)
        return value or ""


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
        value = value.strip()
        if value.startswith('[') and value.endswith(']'):
            try:
                parsed = ast.literal_eval(value)
                if isinstance(parsed, list):
                    return [str(s).replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip() for s in parsed if s]
            except Exception:
                pass
        return [str(s).replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip() for s in value.split(",") if s.strip()]

    def formfield(self, **kwargs):
        defaults = {'form_class': FitSizesFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


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
    description = models.TextField(null=True, blank=True, help_text="Additional style details to show on the product page")
    moq = models.SmallIntegerField(default=15, validators=[MaxValueValidator(9999)], help_text="Minimum order quantity (pcs/style)")

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


# FABRICS CATALOGUE

class FabricType(models.TextChoices):
    REGULAR = "regular", "Regular"
    NEW     = "new",     "New"
    STOCK   = "stock",   "Stock"


class FabricsCatalogue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core fields
    fabric_type = models.CharField(
        max_length=10,
        choices=FabricType.choices,
        help_text="'regular' | 'new' | 'stock' — drives MOQ and enquiry behaviour",
    )
    fabric_name = models.CharField(max_length=200, help_text="Display name of the fabric")
    description = models.TextField(null=True, blank=True, help_text="Additional fabric details")

    # MOQ — driven by fabric_type
    # Regular = 400m, New = 1000m, Stock = no MOQ
    moq_regular = models.IntegerField(default=400, validators=[MaxValueValidator(9999)], help_text="MOQ in meters for Regular fabrics")
    moq_new     = models.IntegerField(default=1000, validators=[MaxValueValidator(9999)], help_text="MOQ in meters for New fabrics")

    # Fabric details
    composition            = models.CharField(max_length=200, null=True, blank=True, help_text="e.g. 100% Cotton")
    width_cm               = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True)
    colour_options         = models.TextField(null=True, blank=True, help_text="Available colour variants")
    price_per_meter        = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_available_meters = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True,
                                                  help_text="Applicable for Stock fabric type only")

    # Status & audit
    is_active  = models.BooleanField(default=True, help_text="Controls visibility on the public Fabrics page")
    created_by = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="created_fabrics",
        help_text="Admin who created the listing",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fabrics_catalogue"
        ordering = ["-created_at"]
        verbose_name = "Fabric"
        verbose_name_plural = "Fabrics Catalogue"
        indexes = [
            models.Index(fields=["fabric_type"], name="idx_fabric_type"),
            models.Index(fields=["is_active"],   name="idx_fabric_active"),
        ]

    def __str__(self):
        return f"{self.fabric_name} ({self.fabric_type})"

    @property
    def effective_moq(self):
        """Returns applicable MOQ based on fabric_type."""
        if self.fabric_type == FabricType.REGULAR:
            return self.moq_regular
        elif self.fabric_type == FabricType.NEW:
            return self.moq_new
        return None  # Stock has no MOQ


class FabricsCatalogueImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    catalogue = models.ForeignKey(
        FabricsCatalogue,
        on_delete=models.CASCADE,
        related_name="images",
        help_text="Parent catalogue entry",
    )

    image        = models.ImageField(upload_to="fabrics/images/", help_text="Fabric swatch or detail image")
    is_thumbnail = models.BooleanField(default=False, help_text="Main swatch display image")
    sort_order   = models.IntegerField(default=0)
    uploaded_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fabrics_catalogue_images"
        ordering = ["-is_thumbnail", "sort_order", "uploaded_at"]
        verbose_name = "Fabric Image"
        verbose_name_plural = "Fabric Images"

    def __str__(self):
        return f"{'Thumbnail' if self.is_thumbnail else 'Image'} — {self.catalogue.fabric_name}"

    def save(self, *args, **kwargs):
        # Ensure only one thumbnail per fabric
        if self.is_thumbnail:
            FabricsCatalogueImage.objects.filter(
                catalogue=self.catalogue, is_thumbnail=True
            ).exclude(pk=self.pk).update(is_thumbnail=False)
        super().save(*args, **kwargs)