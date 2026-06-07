import uuid
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from api_keys.authentication import ApiKeyAuthentication
from empresas.models import Empresa
from dgii.services import emitir_ecf, consultar_estado
from dgii.tasks import reintentar_envio_ecf
from dgii.utils.dgii_client import DgiiClientError
from .models import Comprobante
from .serializers import ComprobanteCreateSerializer, ComprobanteDetalleSerializer
from .services import ComprobantesService, InsufficientQuotaError


class ComprobanteViewSet(viewsets.ModelViewSet):
    queryset = Comprobante.objects.all()
    authentication_classes = [ApiKeyAuthentication]

    def get_serializer_class(self):
        if self.action == "create":
            return ComprobanteCreateSerializer
        return ComprobanteDetalleSerializer

    def _get_empresa(self):
        user = self.request.user
        if isinstance(user, Empresa):
            return user
        return user.empresa

    def get_queryset(self):
        return Comprobante.objects.filter(empresa=self._get_empresa())

    def create(self, request, *args, **kwargs):
        idempotency_key = self._extract_idempotency_key(request)
        if idempotency_key:
            existente = self._check_idempotency(idempotency_key)
            if existente:
                serializer = ComprobanteDetalleSerializer(existente)
                return Response(serializer.data, status=status.HTTP_409_CONFLICT)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        empresa = self._get_empresa()

        if idempotency_key:
            serializer.validated_data["idempotency_key"] = idempotency_key

        try:
            resultado = ComprobantesService.create_comprobante(
                data=serializer.validated_data,
                empresa=empresa,
            )
        except InsufficientQuotaError:
            return Response(
                {"detail": "Cuota agotada."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(resultado, status=status.HTTP_201_CREATED)

    def _extract_idempotency_key(self, request):
        key = request.META.get("HTTP_IDEMPOTENCY_KEY") or request.data.get("idempotency_key")
        if not key:
            return None
        try:
            return uuid.UUID(str(key))
        except (ValueError, AttributeError):
            return None

    def _check_idempotency(self, key):
        return Comprobante.objects.filter(idempotency_key=key).first()

    def partial_update(self, request, *args, **kwargs):
        comprobante = self.get_object()
        if comprobante.estado != "BORRADOR":
            return Response(
                {"detail": "Solo se puede modificar un comprobante en estado BORRADOR."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="consultar-dgii")
    def consultar_dgii(self, request, pk=None):
        comprobante = self.get_object()
        if comprobante.estado_dgii == Comprobante.ESTADO_DGII_SIN_ENVIAR:
            return Response(
                {"detail": "El comprobante nunca ha sido enviado a DGII."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultado = consultar_estado(str(comprobante.id))
        except DgiiClientError as exc:
            return Response(
                {"detail": f"DGII no disponible: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"id": resultado.id, "estado_dgii": resultado.estado_dgii})

    @action(detail=True, methods=["post"], url_path="reintentar")
    def reintentar(self, request, pk=None):
        comprobante = self.get_object()
        with transaction.atomic():
            c = Comprobante.objects.select_for_update().get(pk=comprobante.id)
            if c.estado_dgii not in (
                Comprobante.ESTADO_DGII_ERROR_RED,
                Comprobante.ESTADO_DGII_CONTINGENCIA,
            ):
                return Response(
                    {"detail": "Solo se puede reintentar si estado_dgii es ERROR_RED o CONTINGENCIA."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            c.estado_dgii = Comprobante.ESTADO_DGII_REINTENTANDO
            c.save(update_fields=["estado_dgii", "actualizado_at"])
            task = reintentar_envio_ecf.delay(str(c.id))
            c.celery_task_id = task.id
            c.save(update_fields=["celery_task_id"])
        return Response(
            {"detail": "Reintento encolado.", "task_id": task.id},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"], url_path="emitir")
    def emitir(self, request, pk=None):
        comprobante = self.get_object()
        if comprobante.estado_dgii not in (
            Comprobante.ESTADO_DGII_SIN_ENVIAR,
            Comprobante.ESTADO_DGII_ENVIADO,
        ):
            return Response(
                {"detail": "Solo se puede emitir si estado_dgii es SIN_ENVIAR."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultado = emitir_ecf(str(comprobante.id), forzar_reintento=False)
        except DgiiClientError as exc:
            return Response(
                {
                    "detail": f"Error de conexión con DGII: {exc}",
                    "estado": comprobante.estado,
                    "estado_dgii": comprobante.estado_dgii,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({
            "id": resultado.id,
            "encf": resultado.encf,
            "estado": resultado.estado,
            "estado_dgii": resultado.estado_dgii,
        })
