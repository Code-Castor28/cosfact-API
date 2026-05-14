from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import UsuarioViewSet, RecoverPasswordView

app_name = "users"

router = DefaultRouter()
router.register(r"", UsuarioViewSet, basename="usuario")

urlpatterns = [
    # JWT Auth
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Recuperación (temporal sin email)
    path("recover-password/", RecoverPasswordView.as_view(), name="recover_password"),

    # Resto del CRUD + /me/ generados por el router
    path("", include(router.urls)),
]
