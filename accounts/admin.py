from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserRole, Customer


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering     = ["email"]
    list_display = ["email", "role", "is_active", "is_locked", "created_at"]
    list_filter  = ["role", "is_active"]
    search_fields = ["email"]

    fieldsets = (
        (None,              {"fields": ("email", "password")}),
        ("Role & Status",   {"fields": ("role", "is_active")}),
        ("Lockout",         {"fields": ("failed_login_attempts", "locked_until")}),
        ("Timestamps",      {"fields": ("last_login_at", "created_at", "updated_at")}),
    )
    readonly_fields = ["is_staff", "created_at", "updated_at", "last_login_at"]

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "role"),
        }),
    )

    # NOTE: is_staff is intentionally NOT editable in the admin UI.
    # It is automatically synced from the role field via User.save().
    # admin  → is_staff = True  (can log into admin panel)
    # staff  → is_staff = False (cannot log into admin panel)
    # customer → is_staff = False (cannot log into admin panel)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display  = ["brand_name", "contact_name", "phone", "city", "country", "created_at"]
    list_filter   = ["country", "city"]
    search_fields = ["brand_name", "contact_name", "phone", "user__email"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Linked User",   {"fields": ("user",)}),
        ("Brand Info",    {"fields": ("brand_name", "contact_name", "phone", "alternate_phone")}),
        ("Address",       {"fields": ("address_line1", "address_line2", "city", "state", "pin_code", "country")}),
        ("Audit",         {"fields": ("created_by_admin", "created_at", "updated_at")}),
    )