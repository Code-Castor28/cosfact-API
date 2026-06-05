from rest_framework import viewsets, permissions
from users.models import Usuario
from .models import Plan, Suscripcion, PaqueteComprobantes
from .serializers import PlanSerializer, SuscripcionSerializer, PaqueteComprobantesSerializer
from .permissions import IsSuperAdmin, IsEmpresaOrAdminEmpresaOrSuperAdmin


class PlanViewSet(viewsets.ModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsSuperAdmin()]
        return [IsEmpresaOrAdminEmpresaOrSuperAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not (getattr(user, "is_authenticated", False) and getattr(user, "rol", None) == Usuario.ROL_SUPERADMIN):
            qs = qs.filter(activo=True)
        return qs


class SuscripcionViewSet(viewsets.ModelViewSet):
    queryset = Suscripcion.objects.select_related("empresa", "plan").all()
    serializer_class = SuscripcionSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsSuperAdmin()]
        return [IsEmpresaOrAdminEmpresaOrSuperAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if getattr(user, "rol", None) == Usuario.ROL_SUPERADMIN:
            return qs

        if getattr(user, "rol", None) == Usuario.ROL_ADMIN_EMPRESA:
            return qs.filter(empresa=user.empresa)

        # Acceso por API key (user es Empresa)
        if hasattr(user, "rnc"):
            return qs.filter(empresa=user)

        return qs.none()


class PaqueteComprobantesViewSet(viewsets.ModelViewSet):
    queryset = PaqueteComprobantes.objects.select_related(
        "empresa", "plan", "suscripcion").all()
    serializer_class = PaqueteComprobantesSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsSuperAdmin()]
        return [IsEmpresaOrAdminEmpresaOrSuperAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if getattr(user, "rol", None) == Usuario.ROL_SUPERADMIN:
            return qs

        if getattr(user, "rol", None) == Usuario.ROL_ADMIN_EMPRESA:
            return qs.filter(empresa=user.empresa)

        # Acceso por API key (user es Empresa)
        if hasattr(user, "rnc"):
            return qs.filter(empresa=user)

        return qs.none()
