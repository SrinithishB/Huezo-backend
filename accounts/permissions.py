from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import UserRole


class IsAdmin(BasePermission):
    """Allow access only to admin role."""
    message = "Admin access required."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRole.ADMIN
        )


class IsAdminOrStaff(BasePermission):
    """Allow access to admin or staff users."""
    message = "Admin or staff access required."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in (UserRole.ADMIN, UserRole.STAFF)
        )


class IsAdminOrStaffReadOnly(BasePermission):
    """
    Admin → full access (GET, POST, PUT, PATCH, DELETE)
    Staff → read-only (GET, HEAD, OPTIONS only)
    """
    message = "Admin or staff access required."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role == UserRole.ADMIN:
            return True
        if request.user.role == UserRole.STAFF:
            return request.method in SAFE_METHODS
        return False


class IsCustomer(BasePermission):
    """Allow access only to customer role."""
    message = "Customer access required."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRole.CUSTOMER
        )