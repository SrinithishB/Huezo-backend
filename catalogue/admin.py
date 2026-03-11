from django.contrib import admin
from django.utils.html import format_html
from .models import WLPrototype, WLPrototypeImage


class WLPrototypeImageInline(admin.TabularInline):
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
class WLPrototypeAdmin(admin.ModelAdmin):
    list_display    = [
        "prototype_code", "garment_type", "for_gender",
        "collection_name", "moq", "is_prebooking",
        "is_active", "thumbnail_preview", "created_at",
    ]
    list_filter     = ["for_gender", "is_active", "is_prebooking", "garment_type"]
    search_fields   = ["prototype_code", "garment_type", "collection_name"]
    readonly_fields = ["id", "thumbnail_preview", "created_at", "updated_at"]
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
            "fields": ("moq", "fit_sizes", "customization_available"),
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
        # Auto-assign created_by_admin on first save
        if not change and not obj.created_by_admin:
            obj.created_by_admin = request.user
        super().save_model(request, obj, form, change)


@admin.register(WLPrototypeImage)
class WLPrototypeImageAdmin(admin.ModelAdmin):
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