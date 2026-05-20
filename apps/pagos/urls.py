from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PagoViewSet

app_name = "pagos"

router = DefaultRouter()
router.register(r"pagos", PagoViewSet, basename="pago")

urlpatterns = [
    path("", include(router.urls)),
]
