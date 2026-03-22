from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Customer


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display    = ["email", "role", "is_active", "is_staff", "is_superuser", "created_at"]
    list_filter     = ["role", "is_active", "is_staff"]
    search_fields   = ["email"]
    ordering        = ["-created_at"]
    readonly_fields = [
        "id", "last_login_at", "created_at", "updated_at",
        "failed_login_attempts", "locked_until",
    ]

    fieldsets = (
        ("Account",    {"fields": ("id", "email", "password")}),
        ("Role",       {"fields": ("role",)}),
        ("Status",     {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Lockout",    {"fields": ("failed_login_attempts", "locked_until")}),
        ("Timestamps", {"fields": ("last_login_at", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        ("Create User", {
            "classes": ("wide",),
            "fields":  ("email", "password1", "password2", "role"),
        }),
    )

    # ── Permission gates ──────────────────────────────────────────── #

    def has_add_permission(self, request):
        """Only superadmin can create new users."""
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        """Only superadmin can delete users."""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """
        superadmin → can change anything
        admin      → can change users (e.g. reset password, change role)
                     but cannot promote anyone to superuser (handled in save)
        staff      → read only
        """
        if request.user.is_superuser:
            return True
        if request.user.role == "admin":
            return True
        return False

    def save_model(self, request, obj, form, change):
        """Prevent admin from granting superuser to anyone."""
        if not request.user.is_superuser:
            obj.is_superuser = False   # Admin cannot make someone a superuser
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        """Admin cannot change is_superuser field."""
        rf = list(self.readonly_fields)
        if not request.user.is_superuser:
            rf.append("is_superuser")
        return rf


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display    = ["brand_name", "contact_name", "phone", "user", "city", "created_at"]
    search_fields   = ["brand_name", "contact_name", "phone", "user__email"]
    list_filter     = ["city", "state", "country"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering        = ["-created_at"]

    fieldsets = (
        ("Customer Info", {
            "fields": ("id", "user", "brand_name", "contact_name"),
        }),
        ("Contact", {
            "fields": ("phone", "alternate_phone"),
        }),
        ("Address", {
            "fields": ("address_line1", "address_line2", "city", "state", "pin_code", "country"),
        }),
        ("Audit", {
            "fields": ("created_by_admin", "created_at", "updated_at"),
        }),
    )

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == "admin"

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser