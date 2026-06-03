import uuid
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from api_keys.authentication import ApiKeyAuthentication
from empresas.models import Empresa
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
