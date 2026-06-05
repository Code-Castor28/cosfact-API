from rest_framework import viewsets, permissions
from .catalogs.models import (
    Provincia, Municipio, UnidadMedida, Moneda,
    ImpuestoAdicional, FormaPago,
)
from .serializers import (
    ProvinciaSerializer, MunicipioSerializer, UnidadMedidaSerializer,
    MonedaSerializer, ImpuestoAdicionalSerializer, FormaPagoSerializer,
)
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
