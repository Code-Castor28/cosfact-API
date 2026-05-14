from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from users.models import Usuario
from .models import Secuencial
from .serializers import SecuencialSerializer
from .permissions import IsAdminEmpresaOrSuperAdmin, IsEmpresaOrAdminEmpresaOrSuperAdmin


class SecuencialViewSet(viewsets.ModelViewSet):
    queryset = Secuencial.objects.select_related("empresa").all()
    serializer_class = SecuencialSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "bloquear", "desbloquear"):
            return [permissions.IsAuthenticated(), IsAdminEmpresaOrSuperAdmin()]
        return [IsEmpresaOrAdminEmpresaOrSuperAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if getattr(user, "rol", None) == Usuario.ROL_SUPERADMIN:
            return qs

        if getattr(user, "rol", None) == Usuario.ROL_ADMIN_EMPRESA:
            return qs.filter(empresa=user.empresa)

        if hasattr(user, "rnc"):
            return qs.filter(empresa=user)

        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        empresa = serializer.validated_data.get("empresa")

        if getattr(user, "rol", None) == Usuario.ROL_ADMIN_EMPRESA:
            if empresa and empresa != user.empresa:
                raise PermissionDenied(
                    "No puedes crear secuenciales para otra empresa.")
            serializer.save(empresa=user.empresa)
            return

        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if getattr(user, "rol", None) == Usuario.ROL_ADMIN_EMPRESA:
            instancia = self.get_object()
            if instancia.empresa != user.empresa:
                raise PermissionDenied(
                    "No puedes modificar secuenciales de otra empresa.")
        serializer.save()

    @action(detail=True, methods=["get"], url_path="preview")
    def preview(self, request, pk=None):
        instancia = self.get_object()
        return Response({"proximo_encf": instancia.proximo_encf()}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="bloquear")
    def bloquear(self, request, pk=None):
        instancia = self.get_object()
        motivo = request.data.get("motivo", "Bloqueado desde API")
        instancia.bloqueado = True
        instancia.motivo_bloqueo = motivo
        instancia.save(
            update_fields=["bloqueado", "motivo_bloqueo", "actualizado_at"])
        data = self.get_serializer(instancia).data
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="desbloquear")
    def desbloquear(self, request, pk=None):
        instancia = self.get_object()
        instancia.bloqueado = False
        instancia.motivo_bloqueo = ""
        instancia.save(
            update_fields=["bloqueado", "motivo_bloqueo", "actualizado_at"])
        data = self.get_serializer(instancia).data
        return Response(data, status=status.HTTP_200_OK)
