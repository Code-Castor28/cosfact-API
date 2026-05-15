from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from users.views import RecoverPasswordView

# Rutas de autenticación (separadas para mayor claridad)
urlpatterns = [
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("recover-password/", RecoverPasswordView.as_view(), name="recover_password"),
]
