from rest_framework import permissions
from users.models import Usuario
from empresas.models import Empresa


def _es_empresa(user):
    return isinstance(user, Empresa) or hasattr(user, "rnc")


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "rol", None) == Usuario.ROL_SUPERADMIN
        )


class IsAdminEmpresaOrSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "rol", None) in (Usuario.ROL_SUPERADMIN, Usuario.ROL_ADMIN_EMPRESA)
        )


class IsEmpresaOrAdminEmpresaOrSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if user and getattr(user, "is_authenticated", False):
            if getattr(user, "rol", None) in (Usuario.ROL_SUPERADMIN, Usuario.ROL_ADMIN_EMPRESA):
                return True
        return _es_empresa(user)
