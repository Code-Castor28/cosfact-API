import logging

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from django.utils.crypto import get_random_string

from .models import Usuario
from .serializers import UsuarioSerializer, CambiarPasswordSerializer
from .permissions import IsSuperAdmin

logger = logging.getLogger(__name__)


class UsuarioViewSet(viewsets.ModelViewSet):
    serializer_class = UsuarioSerializer

    def get_permissions(self):
        """
        Instancia y devuelve la lista de permisos que requiere esta vista.
        - Solo SUPERADMIN puede crear (POST) o eliminar (DELETE).
        - ADMIN_EMPRESA puede ver (GET) y actualizar (PUT/PATCH).
        - USUARIO_EMPRESA no puede acceder a este ViewSet (usan /me/).
        """
        if self.action in ["create", "destroy"]:
            permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """
        Filtra el queryset basado en el rol del usuario.
        """
        user = self.request.user

        if user.rol == Usuario.ROL_SUPERADMIN:
            return Usuario.objects.all()
        if user.rol == Usuario.ROL_ADMIN_EMPRESA:
            return Usuario.objects.filter(empresa=user.empresa)
        return Usuario.objects.none()

    def perform_destroy(self, instance):
        """Soft delete (desactivar) en lugar de borrar."""
        instance.is_active = False
        instance.save()

    @action(detail=False, methods=["get", "put", "patch"], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """
        Endpoint para el perfil del usuario autenticado.
        GET /api/v1/users/me/
        PUT /api/v1/users/me/
        """
        user = request.user
        if not isinstance(user, Usuario):
            return Response({"detail": "Este endpoint solo está disponible para usuarios registrados."}, status=status.HTTP_403_FORBIDDEN)
        if request.method == "GET":
            serializer = self.get_serializer(user)
            return Response(serializer.data)

        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            validated_data = serializer.validated_data
            for field in ["rol", "empresa", "is_active", "email"]:
                validated_data.pop(field, None)
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="me/change-password", permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        """
        Endpoint para cambiar la propia contraseña.
        """
        user = request.user
        serializer = CambiarPasswordSerializer(data=request.data)

        if serializer.is_valid():
            if not user.check_password(serializer.validated_data["password_actual"]):
                return Response({"password_actual": ["Contraseña incorrecta."]}, status=status.HTTP_400_BAD_REQUEST)

            user.set_password(serializer.validated_data["password_nueva"])
            user.save()
            return Response({"status": "Contraseña actualizada exitosamente"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from rest_framework.views import APIView


class RecoverPasswordView(APIView):
    """
    Simula la recuperación de contraseña.
    Por ahora no envía email, solo genera un password aleatorio o un token
    y lo retorna (SOLO PARA DESARROLLO).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Debe proveer un email"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = Usuario.objects.get(email=email)
            temp_password = get_random_string(length=12)
            user.set_password(temp_password)
            user.save()

            if settings.DEBUG:
                logger.debug("[DEV ONLY] temp_password: %s", temp_password)

            return Response({
                "mensaje": "Si el correo existe, recibirás instrucciones.",
            })

        except Usuario.DoesNotExist:
            return Response({"mensaje": "Si el email existe, se han enviado las instrucciones."})
