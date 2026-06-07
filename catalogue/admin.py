from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from django.utils.html import format_html
from huezo_backend.admin_mixins import RowActionsMixin
from .models import WLPrototype, WLPrototypeImage

class WLPrototypeForm(forms.ModelForm):
    class Meta:
        model = WLPrototype
        fields = '__all__'
        widgets = {
            'moq': forms.NumberInput(attrs={
                'min': '0',
                'max': '9999',
                'oninput': "if(this.value.length > 4) this.value = this.value.slice(0,4);",
                'style': 'width: 100px;',
            })
        }


class WLPrototypeImageInline(TabularInline):
    model           = WLPrototypeImage
    extra           = 1
    fields          = ["image", "image_preview", "sort_order", "uploaded_at"]
    readonly_fields = ["image_preview", "uploaded_at"]
    ordering        = ["sort_order"]

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px; width:80px; object-fit:cover; border-radius:4px;" />',
                obj.image.url
            )
        return "—"
    image_preview.short_description = "Preview"


@admin.register(WLPrototype)
class WLPrototypeAdmin(RowActionsMixin, ModelAdmin):
    form = WLPrototypeForm
    list_display    = [
        "prototype_code", "garment_type", "for_gender",
        "collection_name", "moq", "is_prebooking",
        "is_active", "thumbnail_preview", "created_at", "row_actions",
    ]
    list_filter     = ["for_gender", "is_active", "is_prebooking", "garment_type"]
    search_fields   = ["prototype_code", "garment_type", "collection_name", "description"]
    readonly_fields = ["id", "thumbnail_preview", "created_by_admin", "created_at", "updated_at"]
    ordering        = ["-created_at"]
    inlines         = [WLPrototypeImageInline]

    fieldsets = (
        ("Identity", {
            "fields": ("id", "prototype_code", "collection_name"),
        }),
        ("Classification", {
            "fields": ("for_gender", "garment_type"),
        }),
        ("Thumbnail", {
            "fields": ("thumbnail", "thumbnail_preview"),
            "description": "Upload the primary display image for this prototype.",
        }),
        ("Order Details", {
            "fields": ("description", "moq", "fit_sizes", "customization_available"),
        }),
        ("Pre-booking", {
            "fields": ("is_prebooking", "prebooking_close_date"),
        }),
        ("Status & Audit", {
            "fields": ("is_active", "created_by_admin", "created_at", "updated_at"),
        }),
    )

    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="height:120px; width:120px; object-fit:cover; border-radius:6px;" />',
                obj.thumbnail.url
            )
        return "No thumbnail uploaded"
    thumbnail_preview.short_description = "Preview"

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_admin:
            obj.created_by_admin = request.user
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_view_permission(request, obj)
        return True

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_change_permission(request, obj)
        return True

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_add_permission(request)
        return True


@admin.register(WLPrototypeImage)
class WLPrototypeImageAdmin(ModelAdmin):
    list_display    = ["prototype", "image_preview", "sort_order", "uploaded_at"]
    list_filter     = ["prototype"]
    ordering        = ["prototype", "sort_order"]
    readonly_fields = ["id", "image_preview", "uploaded_at"]

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px; width:80px; object-fit:cover; border-radius:4px;" />',
                obj.image.url
            )
        return "—"
    image_preview.short_description = "Preview"


# ======================================================================
# FABRICS ADMIN
# ======================================================================

from .models import FabricsCatalogue, FabricsCatalogueImage


class FabricImageInline(TabularInline):
    model           = FabricsCatalogueImage
    extra           = 1
    fields          = ["image", "image_preview", "is_thumbnail", "sort_order", "uploaded_at"]
    readonly_fields = ["image_preview", "uploaded_at"]
    ordering        = ["-is_thumbnail", "sort_order"]

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px;width:80px;object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"
    image_preview.short_description = "Preview"


class FabricsCatalogueForm(forms.ModelForm):
    class Meta:
        model = FabricsCatalogue
        fields = '__all__'
        widgets = {
            'moq_regular': forms.NumberInput(attrs={
                'min': '0',
                'max': '9999',
                'oninput': "if(this.value.length > 4) this.value = this.value.slice(0,4);",
                'style': 'width: 100px;',
            }),
            'moq_new': forms.NumberInput(attrs={
                'min': '0',
                'max': '9999',
                'oninput': "if(this.value.length > 4) this.value = this.value.slice(0,4);",
                'style': 'width: 100px;',
            })
        }

@admin.register(FabricsCatalogue)
class FabricsCatalogueAdmin(RowActionsMixin, ModelAdmin):
    form = FabricsCatalogueForm
    list_display    = [
        "fabric_name", "fabric_type", "effective_moq_display",
        "composition", "price_per_meter", "stock_available_meters",
        "is_active", "thumbnail_preview", "created_at", "row_actions",
    ]
    list_filter     = ["fabric_type", "is_active"]
    search_fields   = ["fabric_name", "composition", "description"]
    readonly_fields = ["id", "thumbnail_preview", "created_by", "created_at", "updated_at"]
    ordering        = ["-created_at"]
    inlines         = [FabricImageInline]

    fieldsets = (
        ("Basic Info", {
            "fields": ("id", "fabric_name", "fabric_type", "description"),
        }),
        ("MOQ", {
            "fields": ("moq_regular", "moq_new"),
            "description": "Regular = 400m | New = 1000m | Stock = no MOQ",
        }),
        ("Fabric Details", {
            "fields": ("composition", "width_cm", "colour_options", "price_per_meter"),
        }),
        ("Stock", {
            "fields": ("stock_available_meters",),
            "description": "Only fill for Stock fabric type.",
        }),
        ("Thumbnail Preview", {
            "fields": ("thumbnail_preview",),
        }),
        ("Status & Audit", {
            "fields": ("is_active", "created_by", "created_at", "updated_at"),
        }),
    )

    def thumbnail_preview(self, obj):
        thumbnail = obj.images.filter(is_thumbnail=True).first()
        if thumbnail and thumbnail.image:
            return format_html(
                '<img src="{}" style="height:120px;width:120px;object-fit:cover;border-radius:6px;" />',
                thumbnail.image.url,
            )
        return "No thumbnail uploaded"
    thumbnail_preview.short_description = "Thumbnail"

    def effective_moq_display(self, obj):
        moq = obj.effective_moq
        return f"{moq}m" if moq else "No MOQ"
    effective_moq_display.short_description = "MOQ"

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_view_permission(request, obj)
        return True

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_change_permission(request, obj)
        return True

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_add_permission(request)
        return True


@admin.register(FabricsCatalogueImage)
class FabricsCatalogueImageAdmin(ModelAdmin):
    list_display    = ["catalogue", "image_preview", "is_thumbnail", "sort_order", "uploaded_at"]
    list_filter     = ["is_thumbnail", "catalogue"]
    ordering        = ["catalogue", "-is_thumbnail", "sort_order"]
    readonly_fields = ["id", "image_preview", "uploaded_at"]

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px;width:80px;object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"
    image_preview.short_description = "Preview"