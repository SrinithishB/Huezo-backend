from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.widgets import UnfoldAdminIntegerFieldWidget
from django.utils.html import format_html
from huezo_backend.admin_mixins import RowActionsMixin
from .models import WLPrototype, WLPrototypeImage

class WLPrototypeForm(forms.ModelForm):
    class Meta:
        model = WLPrototype
        fields = '__all__'
        widgets = {
            'moq': UnfoldAdminIntegerFieldWidget(attrs={
                'min': '0',
                'max': '9999',
                'oninput': "if(this.value.length > 4) this.value = this.value.slice(0,4);",
                'style': 'width: 100px;',
            })
        }


from django.forms import BaseInlineFormSet
from django.core.exceptions import ValidationError

class WLPrototypeImageFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        thumbnail_count = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                if form.cleaned_data.get('is_thumbnail', False):
                    thumbnail_count += 1
        if thumbnail_count > 1:
            raise ValidationError("You can only select one image as the thumbnail.")

class WLPrototypeImageInline(TabularInline):
    model           = WLPrototypeImage
    formset         = WLPrototypeImageFormSet
    extra           = 1
    fields          = ["image", "is_thumbnail", "sort_order", "uploaded_at"]
    readonly_fields = ["uploaded_at"]
    ordering        = ["-is_thumbnail", "sort_order"]

class VendorProductFilter(admin.SimpleListFilter):
    title = "Vendor Product"
    parameter_name = "is_vendor"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            if hasattr(queryset.model, "created_by_admin"):
                return queryset.filter(created_by_admin__role="vendor")
            return queryset.filter(created_by__role="vendor")
        if self.value() == "no":
            if hasattr(queryset.model, "created_by_admin"):
                return queryset.exclude(created_by_admin__role="vendor")
            return queryset.exclude(created_by__role="vendor")
        return queryset


@admin.register(WLPrototype)
class WLPrototypeAdmin(RowActionsMixin, ModelAdmin):
    form = WLPrototypeForm
    list_display    = [
        "prototype_code", "garment_type", "for_gender",
        "collection_name", "moq", "is_prebooking",
        "is_active", "is_vendor_product", "thumbnail_preview", "created_at", "row_actions",
    ]
    list_filter     = ["for_gender", "is_active", "is_prebooking", "garment_type", VendorProductFilter]
    search_fields   = ["prototype_code", "garment_type", "collection_name", "description"]
    readonly_fields = ["id", "created_by_admin", "created_at", "updated_at"]
    ordering        = ["-created_at"]
    inlines         = [WLPrototypeImageInline]

    class Media:
        js = ("js/single_thumbnail.js",)

    fieldsets = (
        ("Identity", {
            "fields": ("id", "prototype_code", "collection_name"),
        }),
        ("Classification", {
            "fields": ("for_gender", "garment_type"),
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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == "vendor":
            return qs.filter(created_by_admin=request.user)
        return qs

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.role == "vendor":
            if obj is not None and obj.created_by_admin != request.user:
                return False
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_view_permission(request, obj)
        return True

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.role == "vendor":
            if obj is not None and obj.created_by_admin != request.user:
                return False
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_change_permission(request, obj)
        return True

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.role == "vendor":
            if obj is not None and obj.created_by_admin != request.user:
                return False
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_delete_permission(request, obj)
        return True

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_add_permission(request)
        return True

    def is_vendor_product(self, obj):
        return obj.created_by_admin is not None and obj.created_by_admin.role == "vendor"
    is_vendor_product.boolean = True
    is_vendor_product.short_description = "Vendor Product"

    def get_list_filter(self, request):
        base_filters = super().get_list_filter(request)
        if request.user.role == "vendor":
            return [f for f in base_filters if f != VendorProductFilter]
        return base_filters


@admin.register(WLPrototypeImage)
class WLPrototypeImageAdmin(ModelAdmin):
    list_display    = ["prototype", "image_preview", "sort_order", "uploaded_at"]
    list_filter     = ["prototype"]
    ordering        = ["prototype", "sort_order"]
    readonly_fields = ["id", "image_preview", "uploaded_at"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == "vendor":
            return qs.filter(prototype__created_by_admin=request.user)
        return qs

    def has_module_permission(self, request):
        if request.user.is_authenticated and request.user.role == "vendor":
            return False
        return super().has_module_permission(request)

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


class FabricsCatalogueImageFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        thumbnail_count = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                if form.cleaned_data.get('is_thumbnail', False):
                    thumbnail_count += 1
        if thumbnail_count > 1:
            raise ValidationError("You can only select one image as the thumbnail.")

class FabricImageInline(TabularInline):
    model           = FabricsCatalogueImage
    formset         = FabricsCatalogueImageFormSet
    extra           = 1
    fields          = ["image", "is_thumbnail", "sort_order", "uploaded_at"]
    readonly_fields = ["uploaded_at"]
    ordering        = ["-is_thumbnail", "sort_order"]


class FabricsCatalogueForm(forms.ModelForm):
    class Meta:
        model = FabricsCatalogue
        fields = '__all__'
        widgets = {
            'moq_regular': UnfoldAdminIntegerFieldWidget(attrs={
                'min': '0',
                'max': '9999',
                'oninput': "if(this.value.length > 4) this.value = this.value.slice(0,4);",
                'style': 'width: 100px;',
            }),
            'moq_new': UnfoldAdminIntegerFieldWidget(attrs={
                'min': '0',
                'max': '9999',
                'oninput': "if(this.value.length > 4) this.value = this.value.slice(0,4);",
                'style': 'width: 100px;',
            }),
            'moq_stock': UnfoldAdminIntegerFieldWidget(attrs={
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
        "fabric_name", "sku", "fabric_type", "effective_moq_display",
        "composition", "price_per_meter", "stock_available_meters",
        "is_active", "is_vendor_product", "thumbnail_preview", "created_at", "row_actions",
    ]
    list_filter     = ["fabric_type", "is_active", VendorProductFilter]
    search_fields   = ["fabric_name", "sku", "composition", "description"]
    readonly_fields = ["id", "created_by", "created_at", "updated_at"]
    ordering        = ["-created_at"]
    inlines         = [FabricImageInline]

    class Media:
        js = ("js/single_thumbnail.js",)

    fieldsets = (
        ("Basic Info", {
            "fields": ("id", "sku", "fabric_name", "fabric_type", "description"),
        }),
        ("MOQ", {
            "fields": ("moq_regular", "moq_new", "moq_stock"),
            "description": "Regular = 400m | New = 1000m | Stock = custom MOQ (0 for no MOQ)",
        }),
        ("Fabric Details", {
            "fields": ("composition", "width", "colour_options", "price_per_meter"),
        }),
        ("Stock", {
            "fields": ("stock_available_meters",),
            "description": "Only fill for Stock fabric type.",
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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == "vendor":
            return qs.filter(created_by=request.user)
        return qs

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.role == "vendor":
            if obj is not None and obj.created_by != request.user:
                return False
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_view_permission(request, obj)
        return True

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.role == "vendor":
            if obj is not None and obj.created_by != request.user:
                return False
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_change_permission(request, obj)
        return True

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.role == "vendor":
            if obj is not None and obj.created_by != request.user:
                return False
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_delete_permission(request, obj)
        return True

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        if request.user.groups.exists() or request.user.user_permissions.exists():
            return super().has_add_permission(request)
        return True

    def is_vendor_product(self, obj):
        return obj.created_by is not None and obj.created_by.role == "vendor"
    is_vendor_product.boolean = True
    is_vendor_product.short_description = "Vendor Product"

    def get_list_filter(self, request):
        base_filters = super().get_list_filter(request)
        if request.user.role == "vendor":
            return [f for f in base_filters if f != VendorProductFilter]
        return base_filters


@admin.register(FabricsCatalogueImage)
class FabricsCatalogueImageAdmin(ModelAdmin):
    list_display    = ["catalogue", "image_preview", "is_thumbnail", "sort_order", "uploaded_at"]
    list_filter     = ["is_thumbnail", "catalogue"]
    ordering        = ["catalogue", "-is_thumbnail", "sort_order"]
    readonly_fields = ["id", "image_preview", "uploaded_at"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == "vendor":
            return qs.filter(catalogue__created_by=request.user)
        return qs

    def has_module_permission(self, request):
        if request.user.is_authenticated and request.user.role == "vendor":
            return False
        return super().has_module_permission(request)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px;width:80px;object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"
    image_preview.short_description = "Preview"