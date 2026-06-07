from rest_framework import viewsets, permissions
from rest_framework.pagination import PageNumberPagination
from .catalogs.models import (
    Provincia, Municipio, UnidadMedida, Moneda,
    ImpuestoAdicional, FormaPago,
)
from .serializers import (
    ProvinciaSerializer, MunicipioSerializer, UnidadMedidaSerializer,
    MonedaSerializer, ImpuestoAdicionalSerializer, FormaPagoSerializer,
    DGIILogSerializer,
)
from .models import DGIILog
from users.models import Usuario


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "rol", None) == Usuario.ROL_SUPERADMIN
        )


class CatalogoViewSet(viewsets.ModelViewSet):
    """Base: GET/POST/PATCH/DELETE solo para SUPERADMIN, lectura para autenticados."""

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsSuperAdmin()]
        return [permissions.IsAuthenticated()]


class ProvinciaViewSet(CatalogoViewSet):
    queryset = Provincia.objects.all()
    serializer_class = ProvinciaSerializer


class MunicipioViewSet(CatalogoViewSet):
    queryset = Municipio.objects.select_related("provincia").all()
    serializer_class = MunicipioSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        provincia = self.request.query_params.get("provincia")
        if provincia:
            qs = qs.filter(provincia_id=provincia)
        return qs


class UnidadMedidaViewSet(CatalogoViewSet):
    queryset = UnidadMedida.objects.all()
    serializer_class = UnidadMedidaSerializer


class MonedaViewSet(CatalogoViewSet):
    queryset = Moneda.objects.all()
    serializer_class = MonedaSerializer


class ImpuestoAdicionalViewSet(CatalogoViewSet):
    queryset = ImpuestoAdicional.objects.all()
    serializer_class = ImpuestoAdicionalSerializer


class FormaPagoViewSet(CatalogoViewSet):
    queryset = FormaPago.objects.all()
    serializer_class = FormaPagoSerializer


class DGIILogPagination(PageNumberPagination):
    page_size = 50
    max_page_size = 200
    page_size_query_param = "page_size"


class DGIILogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DGIILog.objects.select_related("empresa", "comprobante").all()
    serializer_class = DGIILogSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DGIILogPagination
    ordering = ["-creado_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if getattr(user, "rol", None) != Usuario.ROL_SUPERADMIN:
            empresa = getattr(user, "empresa", None)
            if empresa:
                qs = qs.filter(empresa=empresa)
            else:
                qs = qs.none()
        elif empresa_id := self.request.query_params.get("empresa_id"):
            qs = qs.filter(empresa_id=empresa_id)

        comprobante_id = self.request.query_params.get("comprobante_id")
        if comprobante_id:
            qs = qs.filter(comprobante_id=comprobante_id)

        estado = self.request.query_params.get("estado")
        if estado:
            qs = qs.filter(estado_respuesta=estado)

        tipo = self.request.query_params.get("tipo_operacion")
        if tipo:
            qs = qs.filter(tipo_operacion=tipo)

        fecha_desde = self.request.query_params.get("fecha_desde")
        if fecha_desde:
            qs = qs.filter(creado_at__gte=fecha_desde)

        fecha_hasta = self.request.query_params.get("fecha_hasta")
        if fecha_hasta:
            qs = qs.filter(creado_at__lte=fecha_hasta)

        return qs
