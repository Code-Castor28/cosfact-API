from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UsuarioViewSet

app_name = "users"

router = DefaultRouter()
router.register(r"usuarios", UsuarioViewSet, basename="usuario")

urlpatterns = [
    path("", include(router.urls)),
]
