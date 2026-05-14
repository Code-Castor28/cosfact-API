# apps/empresas/permissions.py
"""
Permisos personalizados para la app empresas.
"""
from rest_framework import permissions
from users.models import Usuario


class IsSuperAdmin(permissions.BasePermission):
    """
    Permite acceso solo a usuarios con rol SUPERADMIN.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.rol == Usuario.ROL_SUPERADMIN
        )


class IsSuperAdminOrReadOnlyOwnEmpresa(permissions.BasePermission):
    """
    Permiso a nivel de objeto.
    - Superadmin: acceso total.
    - Admin Empresa: solo puede leer (GET/HEAD/OPTIONS) y solo su propia empresa.
    - Usuario Empresa: sin acceso.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Superadmin siempre pasa
        if user.rol == Usuario.ROL_SUPERADMIN:
            return True
        # Admin Empresa solo métodos seguros (lectura)
        if user.rol == Usuario.ROL_ADMIN_EMPRESA:
            return request.method in permissions.SAFE_METHODS
        # Usuario Empresa: sin acceso
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        # Superadmin: acceso total
        if user.rol == Usuario.ROL_SUPERADMIN:
            return True
        # Admin Empresa: solo su empresa, solo lectura
        if user.rol == Usuario.ROL_ADMIN_EMPRESA:
            return (
                request.method in permissions.SAFE_METHODS
                and obj.pk == user.empresa_id
            )
        return False
