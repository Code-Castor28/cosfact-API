from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlanViewSet, SuscripcionViewSet, PaqueteComprobantesViewSet

app_name = "subscriptions"

router = DefaultRouter()
router.register(r"planes", PlanViewSet, basename="plan")
router.register(r"suscripciones", SuscripcionViewSet, basename="suscripcion")
router.register(r"paquetes", PaqueteComprobantesViewSet, basename="paquete")

urlpatterns = [
    path("", include(router.urls)),
]
