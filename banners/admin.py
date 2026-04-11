from django.contrib import admin
from django.utils.html import format_html

from .models import Banner


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display  = ["title", "image_preview", "sort_order", "is_active", "link_url", "created_at"]
    list_filter   = ["is_active"]
    search_fields = ["title"]
    list_editable = ["sort_order", "is_active"]
    ordering      = ["sort_order", "-created_at"]
    readonly_fields = ["id", "image_preview", "created_by", "created_at", "updated_at"]

    fieldsets = (
        ("Banner", {
            "fields": ("id", "title", "image", "image_preview", "link_url"),
        }),
        ("Display", {
            "fields": ("sort_order", "is_active"),
        }),
        ("Audit", {
            "fields": ("created_by", "created_at", "updated_at"),
        }),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px; max-width:200px; object-fit:cover; border-radius:4px;" />',
                obj.image.url,
            )
        return "—"
    image_preview.short_description = "Preview"

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
