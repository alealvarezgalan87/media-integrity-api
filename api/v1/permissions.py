"""
Custom DRF permissions for multi-tenant access control.
"""

from rest_framework.permissions import BasePermission


class IsOrgMember(BasePermission):
    """User must belong to an organization."""

    message = "You must belong to an organization to access this resource."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.organization is not None
        )


class IsOrgAdmin(BasePermission):
    """User must be an admin of their organization."""

    message = "Only organization admins can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.organization is not None
            and request.user.role == "admin"
        )


class IsOrgAdminOrReadOnly(BasePermission):
    """Admin can write, others can only read."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.role == "admin"
