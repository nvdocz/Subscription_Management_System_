from rest_framework.permissions import BasePermission

from .models import User


class HasRole(BasePermission):
    """Base class for permissions that restrict access to specific roles."""

    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.role in self.allowed_roles)
        )


class IsAdmin(HasRole):
    allowed_roles = (User.Role.ADMIN,)


class IsStaff(HasRole):
    allowed_roles = (User.Role.STAFF,)


class IsCustomer(HasRole):
    allowed_roles = (User.Role.CUSTOMER,)


class IsAdminOrStaff(HasRole):
    allowed_roles = (User.Role.ADMIN, User.Role.STAFF)


class AdminWriteStaffRead(BasePermission):
    """Staff can read, only admins can change."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return user.is_superuser or user.role in (User.Role.ADMIN, User.Role.STAFF)
        return user.is_superuser or user.role == User.Role.ADMIN
