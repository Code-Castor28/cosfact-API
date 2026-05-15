# apps/empresas/permissions.py
"""
Permisos personalizados para la app empresas.
Soporta dos tipos de autenticación:
- JWT (Usuario): roles SUPERADMIN / ADMIN_EMPRESA / USUARIO_EMPRESA.
- API Key (Empresa): solo lectura de su propia empresa.
"""
from rest_framework import permissions
from users.models import Usuario
from .models import Empresa as EmpresaModel


def _es_api_key(user):
    return isinstance(user, EmpresaModel)


class IsSuperAdmin(permissions.BasePermission):
    """
    Permite acceso solo a usuarios con rol SUPERADMIN.
    API Key siempre rechazada.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if _es_api_key(user):
            return False
        return user.rol == Usuario.ROL_SUPERADMIN


class IsSuperAdminOrReadOnlyOwnEmpresa(permissions.BasePermission):
    """
    - API Key (Empresa): solo lectura (GET/HEAD/OPTIONS).
    - Superadmin: acceso total.
    - Admin Empresa: solo lectura de su propia empresa.
    - Usuario Empresa: sin acceso.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if _es_api_key(user):
            return request.method in permissions.SAFE_METHODS
        if user.rol == Usuario.ROL_SUPERADMIN:
            return True
        if user.rol == Usuario.ROL_ADMIN_EMPRESA:
            return request.method in permissions.SAFE_METHODS
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        if _es_api_key(user):
            return request.method in permissions.SAFE_METHODS and obj.pk == user.pk
        if user.rol == Usuario.ROL_SUPERADMIN:
            return True
        if user.rol == Usuario.ROL_ADMIN_EMPRESA:
            return (
                request.method in permissions.SAFE_METHODS
                and obj.pk == user.empresa_id
            )
        return False
