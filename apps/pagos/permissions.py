from rest_framework import permissions

from apps.users.models import Usuario


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.rol == Usuario.ROL_SUPERADMIN
        )


class IsSuperAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user
            and request.user.is_authenticated
            and request.user.rol == Usuario.ROL_SUPERADMIN
        )


class IsAdminEmpresaOrSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.rol == Usuario.ROL_SUPERADMIN:
            return True
        if hasattr(request.user, 'empresa'):
            return obj.empresa == request.user.empresa
        return False