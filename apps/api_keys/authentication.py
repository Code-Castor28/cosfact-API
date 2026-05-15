from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import ApiKey


class ApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Api-Key '):
            return None  # No es este tipo de auth, dejar pasar a otro backend

        token = auth_header[8:]
        api_key = ApiKey.verificar(token)

        if not api_key:
            raise AuthenticationFailed('API Key inválida, revocada o expirada.')

        if not api_key.empresa.activa:
            raise AuthenticationFailed('La empresa asociada a esta API Key está inactiva.')

        # Verificar IP si hay restricción
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR', '')
        )
        if not api_key.ip_permitida(ip):
            raise AuthenticationFailed(f'IP {ip} no autorizada para esta API Key.')

        # Registrar uso (sin bloquear el request)
        api_key.registrar_uso(ip)

        # DRF espera (user, auth) — usamos la empresa como "user" para las vistas API
        return (api_key.empresa, api_key)