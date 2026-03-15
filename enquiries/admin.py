from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Enquiry, EnquiryImage


class EnquiryImageInline(admin.TabularInline):
    model           = EnquiryImage
    extra           = 0
    readonly_fields = ['id', 'image_preview', 'file_name', 'file_size_bytes', 'mime_type', 'uploaded_at']
    fields          = ['image', 'image_preview', 'file_name', 'file_size_bytes', 'mime_type', 'uploaded_at']

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px;width:80px;object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"
    image_preview.short_description = "Preview"


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = [
        'enquiry_number', 'order_type', 'full_name', 'phone',
        'email', 'brand_name', 'status', 'unread_badge',
        'assigned_to_user', 'source_page', 'created_at',
    ]
    list_filter     = ['order_type', 'status', 'source_page', 'is_viewed', 'created_at']
    search_fields   = ['enquiry_number', 'full_name', 'phone', 'email', 'brand_name']
    readonly_fields = ['id', 'enquiry_number', 'created_at', 'updated_at', 'viewed_at']
    ordering        = ['-created_at']
    inlines         = [EnquiryImageInline]

    fieldsets = (
        ("Enquiry Info", {
            "fields": ("id", "enquiry_number", "order_type", "source_page"),
        }),
        ("Contact Details", {
            "fields": ("full_name", "phone", "email", "brand_name",
                       "company_age_years", "annual_revenue"),
        }),
        ("Order Details", {
            "fields": ("total_pieces_required", "message"),
        }),
        ("References", {
            "fields": ("wl_prototype", "fabric", "customer"),
            "description": "WL prototype and fabric are auto-linked from the enquiry source page.",
        }),
        ("Admin Management", {
            "fields": ("status", "assigned_to_user", "admin_notes",
                       "is_viewed", "viewed_at"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def unread_badge(self, obj):
        if not obj.is_viewed:
            return format_html('<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">NEW</span>')
        return "—"
    unread_badge.short_description = "Read"

    def save_model(self, request, obj, form, change):
        # Auto-mark as viewed when admin opens and saves
        if change and not obj.is_viewed:
            obj.is_viewed = True
            obj.viewed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(EnquiryImage)
class EnquiryImageAdmin(admin.ModelAdmin):
    list_display    = ['file_name', 'enquiry', 'image_preview', 'file_size_bytes', 'mime_type', 'uploaded_at']
    search_fields   = ['file_name', 'enquiry__enquiry_number']
    readonly_fields = ['id', 'image_preview', 'uploaded_at']

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px;width:80px;object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"
    image_preview.short_description = "Preview"