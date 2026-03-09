from rest_framework.permissions import BasePermission
from .models import UserRole


class IsAdmin(BasePermission):
    """Allow access only to users with role='admin'."""
    message = "Admin access required."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRole.ADMIN
        )


class IsStaff(BasePermission):
    """Allow access only to users with role='staff'."""
    message = "Staff access required."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRole.STAFF
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


class IsCustomer(BasePermission):
    """Allow access only to users with role='customer'."""
    message = "Customer access required."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRole.CUSTOMER
        )


class IsOwnerOrAdminOrStaff(BasePermission):
    """
    Object-level permission:
    - Admin and Staff can access any object.
    - Customer can only access their own object.
    """
    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role in (UserRole.ADMIN, UserRole.STAFF):
            return True
        # For Customer objects — check ownership
        if hasattr(obj, "user"):
            return obj.user == request.user
        # For User objects
        return obj == request.user