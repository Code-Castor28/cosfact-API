from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, AuthenticationFailed
from users.models import Usuario
from empresas.models import Empresa
from .models import Secuencial
from .serializers import SecuencialSerializer, OnboardingSerializer
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

        user_empresa_id = getattr(user, "empresa_id", None)
        if user_empresa_id:
            return qs.filter(empresa_id=user_empresa_id)

        if hasattr(user, "rnc"):
            return qs.filter(empresa=user)

        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        empresa = serializer.validated_data.get("empresa")

        user_empresa_id = getattr(user, "empresa_id", None)
        if user_empresa_id:
            if empresa and empresa.pk != user_empresa_id:
                raise PermissionDenied(
                    "No puedes crear secuenciales para otra empresa.")
            serializer.save(empresa_id=user_empresa_id)
            return

        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        user_empresa_id = getattr(user, "empresa_id", None)
        if user_empresa_id:
            instancia = self.get_object()
            if instancia.empresa_id != user_empresa_id:
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
        instancia.fecha_bloqueo = timezone.now()
        user = request.user if hasattr(request, "user") and request.user.is_authenticated else None
        if user and hasattr(user, "rol"):
            instancia.usuario_bloqueo = user
        instancia.save(
            update_fields=["bloqueado", "motivo_bloqueo", "fecha_bloqueo", "usuario_bloqueo", "actualizado_at"])
        data = self.get_serializer(instancia).data
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="desbloquear")
    def desbloquear(self, request, pk=None):
        instancia = self.get_object()
        instancia.bloqueado = False
        instancia.motivo_bloqueo = ""
        instancia.fecha_bloqueo = None
        instancia.usuario_bloqueo = None
        instancia.save(
            update_fields=["bloqueado", "motivo_bloqueo", "fecha_bloqueo", "usuario_bloqueo", "actualizado_at"])
        data = self.get_serializer(instancia).data
        return Response(data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def onboarding(request):
    """
    POST /api/v1/secuencias/
    SaaS Guard: registra rangos de e-NCF y opcionalmente certificado.
    Scope requerido: empresa:onboarding (validado en ApiKeyAuthentication).
    """
    serializer = OnboardingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user
    if isinstance(user, Empresa):
        empresa = user
    else:
        empresa = user.empresa

    suscripcion = empresa.suscripciones.filter(estado="ACTIVA").first()
    if not suscripcion or not suscripcion.esta_activa:
        return Response(
            {"error": "La empresa no tiene una suscripción activa."},
            status=status.HTTP_403_FORBIDDEN,
        )

    plan = suscripcion.plan
    volumen_total = sum(item["volumen"] for item in serializer.validated_data["secuencias"])
    if volumen_total > plan.limite_comprobantes:
        return Response(
            {"error": f"Volumen total ({volumen_total}) excede el límite del plan ({plan.limite_comprobantes})."},
            status=status.HTTP_403_FORBIDDEN,
        )

    with transaction.atomic():
        if empresa.onboarding_bloqueado:
            return Response(
                {"error": "Onboarding bloqueado. Deuda pendiente por resolver."},
                status=status.HTTP_403_FORBIDDEN,
            )

        for item in serializer.validated_data["secuencias"]:
            Secuencial.objects.update_or_create(
                empresa=empresa,
                tipo_ecf=item["tipo_ecf"],
                defaults={
                    "minimo_asignado": int(item["desde"][3:]),
                    "maximo_asignado": int(item["hasta"][3:]),
                    "ultimo_numero": int(item["desde"][3:]) - 1,
                },
            )

    return Response(
        {"mensaje": "Onboarding completado exitosamente."},
        status=status.HTTP_201_CREATED,
    )
