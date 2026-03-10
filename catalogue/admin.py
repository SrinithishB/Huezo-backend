from django.contrib import admin
from .models import WLPrototype, WLPrototypeImage


class WLPrototypeImageInline(admin.TabularInline):
    model      = WLPrototypeImage
    extra      = 1
    fields     = ["storage_path", "sort_order", "uploaded_at"]
    readonly_fields = ["uploaded_at"]
    ordering   = ["sort_order"]


@admin.register(WLPrototype)
class WLPrototypeAdmin(admin.ModelAdmin):
    list_display    = [
        "prototype_code", "garment_type", "for_gender",
        "collection_name", "moq", "is_prebooking", "is_active", "created_at",
    ]
    list_filter     = ["for_gender", "is_active", "is_prebooking"]
    search_fields   = ["prototype_code", "garment_type", "collection_name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering        = ["-created_at"]
    inlines         = [WLPrototypeImageInline]

    fieldsets = (
        ("Identity",       {"fields": ("id", "prototype_code", "collection_name")}),
        ("Classification", {"fields": ("for_gender", "garment_type")}),
        ("Media",          {"fields": ("thumbnail_storage_path",)}),
        ("Order Details",  {"fields": ("moq", "fit_sizes", "customization_available")}),
        ("Pre-booking",    {"fields": ("is_prebooking", "prebooking_close_date")}),
        ("Status & Audit", {"fields": ("is_active", "created_by_admin", "created_at", "updated_at")}),
    )


@admin.register(WLPrototypeImage)
class WLPrototypeImageAdmin(admin.ModelAdmin):
    list_display  = ["prototype", "storage_path", "sort_order", "uploaded_at"]
    list_filter   = ["prototype"]
    ordering      = ["prototype", "sort_order"]
    readonly_fields = ["id", "uploaded_at"]