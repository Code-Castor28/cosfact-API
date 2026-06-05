# ─── MIDDLEWARE.PY — apps/audit/middleware.py ───
"""
apps/audit/middleware.py

Dos middlewares críticos:

1. TenantMiddleware:
   Inyecta request.empresa a partir del usuario autenticado (portal web)
   o de la ApiKey (llamadas API). Toda vista que necesite datos de empresa
   llama request.empresa en lugar de buscar la empresa manualmente.
   Esto centraliza el aislamiento multi-tenant.

2. AuditMiddleware:
   Registra cada request al AuditLog automáticamente.
   Ignora endpoints de health check y estáticos.
"""
import hashlib
import json

from django.utils.deprecation import MiddlewareMixin


# ─────────────────────────────────────────────────────────────────────────────
# Tenant Middleware
# ─────────────────────────────────────────────────────────────────────────────

PATHS_SIN_TENANT = {
    "/admin/",
    "/api/auth/login/",
    "/api/auth/token/",
    "/health/",
    "/static/",
    "/media/",
}


class TenantMiddleware(MiddlewareMixin):
    """
    Inyecta request.empresa basado en el actor autenticado.

    Para usuarios del portal web: empresa = usuario.empresa
    Para llamadas API con ApiKey: empresa = api_key.empresa
    Para superadmin: empresa = None (puede ver todo)

    NOTA: Las vistas deben usar request.empresa para filtrar sus QuerySets.
    Nunca hacer Comprobante.objects.all() — siempre Comprobante.objects.filter(empresa=request.empresa).
    """

    def process_request(self, request):
        request.empresa = None

        # No aplicar en paths de sistema
        if any(request.path.startswith(p) for p in PATHS_SIN_TENANT):
            return

        # Caso 1: Usuario autenticado (portal web)
        if hasattr(request, "user") and request.user.is_authenticated:
            from users.models import Usuario
            if request.user.rol == Usuario.ROL_SUPERADMIN:
                request.empresa = None  # Superadmin puede operar sobre todas
            else:
                request.empresa = request.user.empresa
            return

        # Caso 2: ApiKey en el header Authorization
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Api-Key "):
            token = auth_header[8:]
            from api_keys.models import ApiKey
            api_key = ApiKey.verificar(token)
            if api_key:
                request.empresa = api_key.empresa
                request.api_key = api_key  # Para el rate limiter y auditoría
            # Si la key no es válida, request.empresa queda None
            # La vista debe retornar 401


# ─────────────────────────────────────────────────────────────────────────────
# Audit Middleware
# ─────────────────────────────────────────────────────────────────────────────

PATHS_SIN_AUDIT = {"/health/", "/static/", "/media/", "/favicon.ico"}

# Métodos que no vale la pena auditar
METODOS_SIN_AUDIT = {"OPTIONS", "HEAD"}


class AuditMiddleware(MiddlewareMixin):
    """
    Registra automáticamente cada request relevante en AuditLog.
    Solo registra después del response (process_response) para tener el status code.
    No registra bodies completos — solo su SHA-256 para no guardar datos sensibles.
    """

    def process_response(self, request, response):
        try:
            if request.method in METODOS_SIN_AUDIT:
                return response
            if any(request.path.startswith(p) for p in PATHS_SIN_AUDIT):
                return response

            # Determinar actor
            usuario = None
            api_key_prefix = ""
            empresa = getattr(request, "empresa", None)

            if hasattr(request, "user") and request.user.is_authenticated:
                usuario = request.user
            if hasattr(request, "api_key"):
                api_key_prefix = request.api_key.prefix

            # Hash del body (no el body completo)
            body_hash = ""
            if request.method in ("POST", "PUT", "PATCH"):
                try:
                    body = request.body
                    body_hash = hashlib.sha256(body).hexdigest() if body else ""
                except Exception:
                    pass

            # IP real (detrás de proxy/Nginx)
            ip = (
                request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                or request.META.get("REMOTE_ADDR", "")
            )

            from audit.models import AuditLog
            AuditLog.objects.create(
                empresa=empresa,
                usuario=usuario,
                api_key_prefix=api_key_prefix,
                accion=_metodo_a_accion(request.method),
                endpoint=request.path[:255],
                metodo_http=request.method,
                ip=ip or None,
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                request_body_hash=body_hash,
                response_status=response.status_code,
            )
        except Exception:
            # El middleware de auditoría NUNCA debe romper el request principal
            pass

        return response


def _metodo_a_accion(metodo: str) -> str:
    return {
        "GET": "READ",
        "POST": "CREATE",
        "PUT": "UPDATE",
        "PATCH": "UPDATE",
        "DELETE": "DELETE",
    }.get(metodo, "READ")
