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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        empresa = self._get_empresa()

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

    def partial_update(self, request, *args, **kwargs):
        comprobante = self.get_object()
        if comprobante.estado != "BORRADOR":
            return Response(
                {"detail": "Solo se puede modificar un comprobante en estado BORRADOR."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)
