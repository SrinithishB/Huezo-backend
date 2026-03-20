from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserRole, Customer


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering      = ["email"]
    list_display  = ["email", "role", "is_active", "is_locked", "created_at"]
    list_filter   = ["role", "is_active"]
    search_fields = ["email"]

    fieldsets = (
        (None,            {"fields": ("email", "password")}),
        ("Role & Status", {"fields": ("role", "is_active")}),
        ("Lockout",       {"fields": ("failed_login_attempts", "locked_until")}),
        ("Timestamps",    {"fields": ("last_login_at", "created_at", "updated_at")}),
    )
    readonly_fields = ["is_staff", "created_at", "updated_at", "last_login_at"]

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "role"),
        }),
    )

    # Grant view + change permissions to all admin users
    def has_view_permission(self, request, obj=None):   return True
    def has_change_permission(self, request, obj=None): return True
    def has_add_permission(self, request):              return True
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser


class CustomerUserRawIdWidget(admin.widgets.ForeignKeyRawIdWidget):
    """Limits the user popup to customer-role users only."""
    def url_parameters(self):
        params = super().url_parameters()
        params['role'] = 'customer'
        return params


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display  = ["brand_name", "contact_name", "phone", "city", "country", "created_at"]
    list_filter   = ["country", "city"]
    search_fields = ["brand_name", "contact_name", "phone", "user__email"]
    readonly_fields = ["created_at", "updated_at", "created_by_admin"]

    fieldsets = (
        ("Linked User",   {"fields": ("user",)}),
        ("Brand Info",    {"fields": ("brand_name", "contact_name", "phone", "alternate_phone")}),
        ("Address",       {"fields": ("address_line1", "address_line2", "city", "state", "pin_code", "country")}),
        ("Audit",         {"fields": ("created_by_admin", "created_at", "updated_at")}),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Limit the user dropdown to customer-role users only
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(role=UserRole.CUSTOMER).order_by("email")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Auto-assign created_by_admin on first save
        if not change and not obj.created_by_admin:
            obj.created_by_admin = request.user
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):   return True
    def has_change_permission(self, request, obj=None): return True
    def has_add_permission(self, request):              return True