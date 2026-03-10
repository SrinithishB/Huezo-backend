from django.contrib import admin
from .models import Enquiry, EnquiryImage


class EnquiryImageInline(admin.TabularInline):
    model = EnquiryImage
    extra = 0
    readonly_fields = ('file_name','storage_path','file_size_bytes','mime_type','uploaded_at')


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ('enquiry_number','order_type','full_name','phone','email','brand_name','status','is_viewed','source_page','created_at')

    list_filter = ('order_type','status','source_page','is_viewed','created_at')

    search_fields = ('enquiry_number','full_name','phone','email','brand_name')

    readonly_fields = ('id','enquiry_number','created_at','updated_at','viewed_at')

    inlines = [EnquiryImageInline]


@admin.register(EnquiryImage)
class EnquiryImageAdmin(admin.ModelAdmin):
    list_display = ('file_name','enquiry','file_size_bytes','mime_type','uploaded_at')

    search_fields = ('file_name','enquiry__enquiry_number')

    readonly_fields = ('id','uploaded_at')