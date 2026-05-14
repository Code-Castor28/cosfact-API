# apps/empresas/api_views.py
"""
API REST para la app empresas.

REGLAS DE SEGURIDAD:
  - Superadmin: CRUD completo sobre cualquier empresa.
  - Admin Empresa: solo GET de su propia empresa y sus endpoints /suscripcion/ y /comprobantes/.
  - Usuario Empresa: sin acceso (403).
  - Soft delete obligatorio — nunca borrado físico.
  - El campo `ambiente` es de solo lectura para Admin Empresa.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound

from users.models import Usuario
from subscriptions.models import Suscripcion, PaqueteComprobantes

from .models import Empresa
from .permissions import IsSuperAdmin, IsSuperAdminOrReadOnlyOwnEmpresa
from .serializers import (
    EmpresaListSerializer,
    EmpresaDetailSerializer,
    EmpresaWriteSerializer,
    EmpresaAdminSerializer,
    SuscripcionResumenSerializer,
    PaqueteResumenSerializer,
)


class EmpresaViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para el modelo Empresa.

    Endpoints generados por el router:
      GET    /api/v1/empresas/            → list    (solo Superadmin)
      POST   /api/v1/empresas/            → create  (solo Superadmin)
      GET    /api/v1/empresas/{id}/       → retrieve (Superadmin o Admin de esa empresa)
      PATCH  /api/v1/empresas/{id}/       → partial_update (solo Superadmin)
      DELETE /api/v1/empresas/{id}/       → destroy  (soft delete, solo Superadmin)

    Endpoints custom:
      GET    /api/v1/empresas/{id}/suscripcion/   → suscripción activa
      GET    /api/v1/empresas/{id}/comprobantes/  → paquetes de comprobantes activos
    """

    # ── Permisos ──────────────────────────────────────────────────────────────

    def get_permissions(self):
        """
        Asigna permisos según la acción:
        - Escritura (create, update, destroy): solo Superadmin.
        - Lectura y endpoints custom: Superadmin o Admin de su empresa.
        """
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [permissions.IsAuthenticated(), IsSuperAdmin()]
        # list, retrieve, suscripcion, comprobantes
        return [permissions.IsAuthenticated(), IsSuperAdminOrReadOnlyOwnEmpresa()]

    # ── QuerySet ──────────────────────────────────────────────────────────────

    def get_queryset(self):
        """
        Filtra según el rol del usuario autenticado.
        - Superadmin → todas las empresas (excluye soft-deleted por defecto).
        - Admin Empresa → solo su empresa.
        - Otros → nada.
        """
        user = self.request.user

        if user.rol == Usuario.ROL_SUPERADMIN:
            qs = Empresa.objects.all()
            # Parámetro opcional ?incluir_eliminadas=true para auditoría
            if self.request.query_params.get('incluir_eliminadas') == 'true':
                return qs
            return qs.filter(deleted_at__isnull=True)

        if user.rol == Usuario.ROL_ADMIN_EMPRESA:
            if user.empresa_id:
                return Empresa.objects.filter(pk=user.empresa_id, deleted_at__isnull=True)
            return Empresa.objects.none()

        return Empresa.objects.none()

    # ── Serializers ───────────────────────────────────────────────────────────

    def get_serializer_class(self):
        """
        Retorna el serializer adecuado según rol y acción.
        """
        user = self.request.user

        # Escritura — solo Superadmin llega aquí
        if self.action in ('create', 'update', 'partial_update'):
            return EmpresaWriteSerializer

        # Lectura para Admin Empresa
        if user.rol == Usuario.ROL_ADMIN_EMPRESA:
            return EmpresaAdminSerializer

        # Lectura Superadmin: list usa el serializer compacto, retrieve el completo
        if self.action == 'list':
            return EmpresaListSerializer

        return EmpresaDetailSerializer

    # ── Acciones CRUD ─────────────────────────────────────────────────────────

    def perform_destroy(self, instance):
        """
        Soft delete — llama al .delete() del modelo que ya hace el manejo correcto.
        Nunca se borra físicamente (retención legal DGII 10 años).
        """
        instance.delete()

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _get_empresa_or_403(self, pk):
        """
        Obtiene una empresa verificando que el usuario tenga acceso a ella.
        Superadmin: cualquier empresa.
        Admin Empresa: solo la suya.
        Lanza PermissionDenied o NotFound según corresponda.
        """
        user = self.request.user

        try:
            empresa = Empresa.objects.get(pk=pk, deleted_at__isnull=True)
        except Empresa.DoesNotExist:
            raise NotFound("Empresa no encontrada.")

        if user.rol == Usuario.ROL_SUPERADMIN:
            return empresa

        if user.rol == Usuario.ROL_ADMIN_EMPRESA:
            if str(empresa.pk) == str(user.empresa_id):
                return empresa
            raise PermissionDenied("No tienes acceso a esta empresa.")

        raise PermissionDenied("No tienes permisos para esta acción.")

    # ── Endpoints Custom ──────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='suscripcion')
    def suscripcion(self, request, pk=None):
        """
        GET /api/v1/empresas/{id}/suscripcion/
        Devuelve la suscripción activa más reciente de la empresa.
        Acceso: Superadmin + Admin de esa empresa.
        """
        empresa = self._get_empresa_or_403(pk)

        suscripcion = (
            Suscripcion.objects
            .filter(empresa=empresa, estado=Suscripcion.ESTADO_ACTIVA)
            .select_related('plan')
            .order_by('-creado_at')
            .first()
        )

        if not suscripcion:
            return Response(
                {"detail": "Esta empresa no tiene una suscripción activa."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SuscripcionResumenSerializer(suscripcion)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='comprobantes')
    def comprobantes(self, request, pk=None):
        """
        GET /api/v1/empresas/{id}/comprobantes/
        Devuelve los paquetes de comprobantes activos de la empresa (orden FIFO).
        Acceso: Superadmin + Admin de esa empresa.
        """
        empresa = self._get_empresa_or_403(pk)

        paquetes = (
            PaqueteComprobantes.objects
            .filter(empresa=empresa, estado=PaqueteComprobantes.ESTADO_ACTIVO)
            .order_by('fecha_compra')  # FIFO
        )

        serializer = PaqueteResumenSerializer(paquetes, many=True)
        return Response({
            "empresa_id": str(empresa.pk),
            "empresa_rnc": empresa.rnc,
            "total_paquetes_activos": paquetes.count(),
            "paquetes": serializer.data,
        })
