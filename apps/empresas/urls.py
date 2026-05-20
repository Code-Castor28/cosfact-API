from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmpresaViewSet

app_name = "empresas"

router = DefaultRouter()
router.register(r"empresas", EmpresaViewSet, basename="empresa")

urlpatterns = [
    path("", include(router.urls)),
]
