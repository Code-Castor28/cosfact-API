from rest_framework import permissions

class IsSuperAdmin(permissions.BasePermission):
    """
    Permite acceso solo a los usuarios con rol SUPERADMIN.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol == 'SUPERADMIN')


class IsAdminEmpresa(permissions.BasePermission):
    """
    Permite acceso a los usuarios con rol ADMIN_EMPRESA.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol == 'ADMIN_EMPRESA')


class IsUsuarioEmpresa(permissions.BasePermission):
    """
    Permite acceso a los usuarios con rol USUARIO_EMPRESA.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol == 'USUARIO_EMPRESA')
