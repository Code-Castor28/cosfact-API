import re

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import ApiKey

SCOPE_PATTERNS = [
    (re.compile(r"^POST /api/v1/comprobantes/$"),            "comprobantes:crear"),
    (re.compile(r"^GET  /api/v1/comprobantes/"),             "comprobantes:consultar"),
    (re.compile(r"^GET  /api/v1/secuenciales/"),             "secuenciales:consultar"),
    (re.compile(r"^POST /api/v1/secuencias/$"),              "empresa:onboarding"),
]


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

        # Validar scope
        self._validar_scope(api_key, request)

        # Registrar uso (sin bloquear el request)
        api_key.registrar_uso(ip)

        # DRF espera (user, auth) — usamos la empresa como "user" para las vistas API
        return (api_key.empresa, api_key)

    def _validar_scope(self, api_key, request):
        ruta = f"{request.method} {request.path}"
        for pattern, scope_requerido in SCOPE_PATTERNS:
            if pattern.match(ruta):
                if not api_key.tiene_scope(scope_requerido):
                    raise AuthenticationFailed(
                        f"Scope '{scope_requerido}' requerido para este endpoint."
                    )
                break