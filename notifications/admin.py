from django.contrib import admin
from .models import FCMDevice, Notification
 
 
@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display    = ["user", "device_id", "is_active", "created_at", "updated_at"]
    list_filter     = ["is_active"]
    search_fields   = ["user__email", "device_id", "fcm_token"]
    readonly_fields = ["id", "fcm_token", "created_at", "updated_at"]
    ordering        = ["-created_at"]
 
    actions = ["deactivate_tokens", "activate_tokens"]
 
    @admin.action(description="Deactivate selected tokens")
    def deactivate_tokens(self, request, queryset):
        queryset.update(is_active=False)
 
    @admin.action(description="Activate selected tokens")
    def activate_tokens(self, request, queryset):
        queryset.update(is_active=True)
 
 
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display    = ["user", "title", "is_read", "created_at"]
    list_filter     = ["is_read"]
    search_fields   = ["user__email", "title", "body"]
    readonly_fields = ["id", "user", "title", "body", "data", "created_at"]
    ordering        = ["-created_at"]