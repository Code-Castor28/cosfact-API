from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import models

from users.permissions import IsSuperAdmin
from .models import ApiKey
from .serializers import ApiKeyReadSerializer, ApiKeyWriteSerializer


class ApiKeyViewSet(viewsets.ModelViewSet):
    """
    Endpoints API Keys (solo SUPERADMIN):
        GET    /api/v1/api-keys/
        POST   /api/v1/api-keys/
        GET    /api/v1/api-keys/{id}/
        PATCH  /api/v1/api-keys/{id}/
        PUT    /api/v1/api-keys/{id}/
        DELETE /api/v1/api-keys/{id}/  (revoca)
        POST   /api/v1/api-keys/{id}/revocar/
        POST   /api/v1/api-keys/{id}/rotar/
    """
    queryset = ApiKey.objects.select_related(
        "empresa", "creado_por", "revocado_por"
    ).all()

    def get_queryset(self):
        qs = super().get_queryset()

        empresa_id = self.request.query_params.get("empresa")
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)

        activa = self.request.query_params.get("activa")
        if activa in ("true", "false"):
            qs = qs.filter(activa=(activa == "true"))

        expirada = self.request.query_params.get("expirada")
        if expirada in ("true", "false"):
            ahora = timezone.now()
            if expirada == "true":
                qs = qs.filter(expira_at__isnull=False, expira_at__lt=ahora)
            else:
                qs = qs.filter(models.Q(expira_at__isnull=True)
                               | models.Q(expira_at__gte=ahora))

        prefix = self.request.query_params.get("prefix")
        if prefix:
            qs = qs.filter(prefix__icontains=prefix)

        nombre = self.request.query_params.get("nombre")
        if nombre:
            qs = qs.filter(nombre__icontains=nombre)
        return qs.order_by("-creado_at")

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsSuperAdmin()]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ApiKeyWriteSerializer
        return ApiKeyReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instancia = serializer.save()

        data = ApiKeyReadSerializer(
            instancia, context=self.get_serializer_context()).data
        data["token"] = getattr(instancia, "_token_completo", None)
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        instancia = self.get_object()
        motivo = request.data.get("motivo", "Revocada desde API")
        if instancia.activa:
            instancia.revocar(revocado_por=request.user, motivo=motivo)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="revocar")
    def revocar(self, request, pk=None):
        instancia = self.get_object()
        motivo = request.data.get("motivo", "Revocada desde API")
        if instancia.activa:
            instancia.revocar(revocado_por=request.user, motivo=motivo)
        data = ApiKeyReadSerializer(
            instancia, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="rotar")
    def rotar(self, request, pk=None):
        instancia = self.get_object()
        nombre = request.data.get("nombre") or f"{instancia.nombre} (rotada)"
        expira_at = request.data.get("expira_at", instancia.expira_at)

        nueva_key, token = ApiKey.crear(
            empresa=instancia.empresa,
            nombre=nombre,
            creado_por=request.user,
            scopes=instancia.scopes,
            allowed_ips=instancia.allowed_ips,
            rate_limit_cantidad=instancia.rate_limit_cantidad,
            rate_limit_ventana=instancia.rate_limit_ventana,
            expira_at=expira_at,
        )

        if instancia.activa:
            instancia.revocar(revocado_por=request.user,
                              motivo="Rotada desde API")

        data = ApiKeyReadSerializer(
            nueva_key, context=self.get_serializer_context()).data
        data["token"] = token
        data["key_revocada_id"] = str(instancia.pk)
        return Response(data, status=status.HTTP_201_CREATED)
