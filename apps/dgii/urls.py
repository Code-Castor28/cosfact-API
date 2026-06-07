from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProvinciaViewSet, MunicipioViewSet, UnidadMedidaViewSet,
    MonedaViewSet, ImpuestoAdicionalViewSet, FormaPagoViewSet,
    DGIILogViewSet,
)

app_name = "dgii"

router = DefaultRouter()
router.register(r"provincias", ProvinciaViewSet, basename="provincia")
router.register(r"municipios", MunicipioViewSet, basename="municipio")
router.register(r"unidades-medida", UnidadMedidaViewSet, basename="unidad-medida")
router.register(r"monedas", MonedaViewSet, basename="moneda")
router.register(r"impuestos-adicionales", ImpuestoAdicionalViewSet, basename="impuesto-adicional")
router.register(r"formas-pago", FormaPagoViewSet, basename="forma-pago")
router.register(r"dgii/logs", DGIILogViewSet, basename="dgii-log")

urlpatterns = [
    path("", include(router.urls)),
]
