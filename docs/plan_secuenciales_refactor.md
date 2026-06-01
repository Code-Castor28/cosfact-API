# Plan: Refactor Secuenciales + POS-Ready Validator

> **Contexto general:** Ver [`plan_fase2.md`](./plan_fase2.md) — **Hito 0.5 — POS-Ready (prerrequisito del Hito 1)**.
> **Documento hermano:** [`plan_webhook_snapshot.md`](./plan_webhook_snapshot.md) — Webhook `empresa.snapshot` (snapshot pesado, push diario al POS).
>
> **Principio de diseño:** El POS cachea localmente el snapshot pesado que recibe por webhook. Antes de cada emisión, valida con `pos/ready/` (validator ligero) sin descargar todo el payload. Esta separación evita overhead en cada comprobante.

---

## 🎯 Objetivo

1. Permitir que el **POS (API-Key)** haga configuración operativa de su empresa:
   - Cargar certificado digital (`POST /api/v1/certificados/` con `.p12` + `pin_texto_plano`).
   - Registrar/actualizar secuenciales (rango autorizado).
2. Restringir el resto de operaciones administrativas a **JWT SUPERADMIN**.
3. Exponer `GET /api/v1/pos/ready/?tipo_ecf=N` como **validator ligero** con payload enriquecido para diagnóstico diario.

---

## 🏗️ Alcance

- Refactor de `apps/sequences/views.py::SecuencialViewSet.get_permissions()` para que **API-Key** pueda `create`/`update`/`partial_update` secuenciales, y el resto sea **SUPERADMIN**.
- App nueva `apps/pos/` con `PosReadyView` (validator ligero) + `services.py` (lógica testeable).
- Multi-tenant estricto: API-Key solo opera datos de su empresa.
- Sin cambios al modelo `Secuencial` (ya existente).
- Sin cambios a los modelos `Suscripcion` / `PaqueteComprobantes` (se usan sus properties ya existentes).
- El endpoint existente de certificados (`/api/v1/certificados/`) se protege con API-Key (no se crean rutas nuevas tipo `/api/v1/pos/certificado/`).

---

## ❌ Fuera de alcance

- Lógica de firma de XMLs (Hito 3 de Fase 2, server-side).
- Snapshot pesado por webhook ([`plan_webhook_snapshot.md`](./plan_webhook_snapshot.md)).
- CRUD de comprobantes (Hito 1 de Fase 2).
- Dispatcher completo de webhooks (Hito 4 de Fase 2).

---

## 📁 Archivos

### Nuevos

| Archivo | Contenido |
|---------|-----------|
| `apps/pos/__init__.py` | Paquete vacío |
| `apps/pos/apps.py` | `PosConfig(AppConfig)` con `name = "pos"` y `default_auto_field = "uuid"` |
| `apps/pos/permissions.py` | `IsPosOnly` + `HasPosReadyScope` (solo API-Key) |
| `apps/pos/services.py` | `validar_pos_ready(empresa, tipo_ecf)` — función pura, sin DRF, retorna dict con `{status, ...payload}` |
| `apps/pos/views.py` | `PosReadyView(APIView)` — capa fina que extrae params, resuelve `empresa`, llama al service y mapea status code |
| `apps/pos/urls.py` | `path("pos/ready/", PosReadyView.as_view(), name="pos-ready")` |
| `apps/pos/tests.py` | Tests de integración del endpoint (~17) |

> **Nota:** No se crea `apps/pos/migrations/` porque la app no tiene modelos. Django no requiere migrations para apps vacías. Si `makemigrations` se queja, se crea con `__init__.py` vacío.

### Modificados

| Archivo | Cambio |
|---------|--------|
| `apps/sequences/views.py` | Permisos ajustados: **API-Key** puede `create`/`update`/`partial_update` secuenciales. **SUPERADMIN** controla el resto. |
| `apps/sequences/tests.py` | 12 tests de permisos por acción (estaba vacío) |
| `apps/api_keys/models.py` | Agregar `"pos:ready"` a `ApiKey.SCOPES_VALIDOS` (en el choices list) |
| `core/settings/base.py` | `INSTALLED_APPS += ["pos"]` + nuevo throttle class `PosReadyThrottle` con rate `60/min` |
| `core/urls.py` | `include("apps.pos.urls")` bajo `/api/v1/` |
| `docs/integracion.md` | Sección 11.9: secuenciales (API-Key solo create/update). Sección 12: `pos/ready/` con payload enriquecido. Sección 10: certificados protegidos por API-Key. |

---

## 🔐 Permisos

### `SecuencialViewSet.get_permissions()`

```python
def get_permissions(self):
    # POS (API-Key) solo puede crear/actualizar secuenciales.
    if self.action in ("create", "update", "partial_update"):
        return [IsPosApiKeyOnly()]
    # Todo lo demás es SUPERADMIN (JWT)
    return [IsSuperAdminOnly()]
```

> **Nota:** Se elimina el acceso de `ADMIN_EMPRESA` a los endpoints de POS. En producción, el POS solo usa API-Key.

| Acción | Permiso efectivo | Quien puede |
|--------|------------------|-------------|
| `create` | `IsPosApiKeyOnly` | Solo API-Key (Empresa) |
| `update` / `partial_update` | `IsPosApiKeyOnly` | Solo API-Key (Empresa) |
| `list` | `IsSuperAdminOnly` | Solo JWT SUPERADMIN |
| `retrieve` | `IsSuperAdminOnly` | Solo JWT SUPERADMIN |
| `preview` | `IsSuperAdminOnly` | Solo JWT SUPERADMIN |
| `destroy` | `IsSuperAdminOnly` | Solo JWT SUPERADMIN |
| `bloquear` / `desbloquear` | `IsSuperAdminOnly` | Solo JWT SUPERADMIN |

### `apps/pos/permissions.py::IsPosOnly`

```python
from rest_framework import permissions
from empresas.models import Empresa


class IsPosOnly(permissions.BasePermission):
    """
    Solo acepta Empresa (request.user es Empresa cuando viene con Api-Key).
    JWT no aplica para el ecosistema POS en producción.
    """
    message = "Autenticación requerida (Api-Key)."

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return isinstance(user, Empresa) or hasattr(user, "rnc")
```

### `apps/pos/permissions.py::HasPosReadyScope`

```python
class HasPosReadyScope(permissions.BasePermission):
    """
    Valida que la API-Key tenga scope 'pos:ready'.
    Solo aplica a API-Key.
    """
    message = "La API-Key no tiene el scope requerido: pos:ready."

    def has_permission(self, request, view):
        # Api-Key: request.auth es la ApiKey instance
        api_key = getattr(request, "auth", None)
        if api_key is None:
            return True  # No es Api-Key, otro check lo manejará
        return api_key.tiene_scope("pos:ready")
```
 
### `apps/pos/permissions.py::IsPosApiKeyOnly` (nuevo — usado en SecuencialViewSet)

```python
class IsPosApiKeyOnly(permissions.BasePermission):
    """
    Solo acepta Empresa autenticada vía API-Key.
    Usado para permitir que el POS cree/actualice secuenciales.
    """
    message = "Solo disponible para POS (API-Key)."

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return isinstance(user, Empresa) or hasattr(user, "rnc")
```

### `IsSuperAdminOnly` (nuevo — usado en SecuencialViewSet)

```python
from rest_framework import permissions
from users.models import Usuario


class IsSuperAdminOnly(permissions.BasePermission):
    """
    Solo SUPERADMIN (JWT) puede acceder.
    Usado para listar, ver detalle, bloquear/desbloquear secuenciales.
    """
    message = "Solo disponible para SUPERADMIN."

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return getattr(user, "rol", None) == Usuario.ROL_SUPERADMIN
```

---

## 🚦 Throttling

### `apps/pos/throttles.py` (nuevo)

```python
from rest_framework.throttling import SimpleRateThrottle


class PosReadyThrottle(SimpleRateThrottle):
    """
    Rate limit específico para /api/v1/pos/ready/.
    60 requests/minuto por API-Key.
    """
    scope = "pos_ready"

    def get_cache_key(self, request, view):
        # request.auth es la ApiKey cuando viene con Api-Key
        if getattr(request, "auth", None) and hasattr(request.auth, "id"):
            return f"pos_ready_key_{request.auth.id}"
        return self.get_ident(request)
```

### Configuración en `core/settings/base.py`

```python
REST_FRAMEWORK = {
    # ... existing ...
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/hour',
        'user': '1000/hour',
        'pos_ready': '60/min',  # NUEVO
    },
}
```

Y en `PosReadyView`:

```python
throttle_classes = [PosReadyThrottle]
```

> **Justificación del rate 60/min:** Una tienda concurrida con 1 POS puede emitir ~1 comprobante cada 3-5 segundos en hora pico. 60/min da margen sin saturar la DB. Si el POS cachea el snapshot pesado (Hito 0.6) y solo llama `pos/ready/` antes de cada emisión, el patrón de uso es ~5-10 req/min típicos, 30 en picos. 60/min es 2x el peor caso esperado.

---

## 📡 Endpoint: `GET /api/v1/pos/ready/`

### Definición

| Atributo | Valor |
|----------|-------|
| **URL** | `/api/v1/pos/ready/` |
| **Método** | `GET` |
| **Permisos** | `IsPosOnly` + `HasPosReadyScope` |
| **Throttle** | `PosReadyThrottle` (60/min) |
| **Auth** | `Api-Key <token>` (POS) |
| **Query params** | `tipo_ecf` (requerido, int ∈ `TIPOS_ECF`) |

### Request

```http
GET /api/v1/pos/ready/?tipo_ecf=31
Authorization: Api-Key 131793916_xxxxxxxxxxxxxxxxx
```

### Response 200 (todo OK)

```json
{
  "puede_emitir": true,
  "certificado": {
    "estatus": "valido",
    "dias_restantes": 45
  },
  "alertas_secuenciales": [],
  "validado_en": "2026-06-01T14:32:11Z"
}
```

### Response 200 con advertencias (puede emitir, pero el POS debe notificar al cajero)

```json
{
  "puede_emitir": true,
  "certificado": {
    "estatus": "valido",
    "dias_restantes": 25
  },
  "alertas_secuenciales": [
    {
      "tipo_ecf": 31,
      "disponibles": 12,
      "alerta": "CRÍTICO: Secuenciales próximos a agotarse"
    }
  ],
  "validado_en": "2026-06-01T14:32:11Z"
}
```

### Errores

Todos los errores usan la forma:

```json
{
  "detail": "Mensaje humano-legible",
  "code": "CODIGO_MAQUINA"
}
```

| Status | Code | Cuándo | Acción sugerida al POS |
|--------|------|--------|--------------------------|
| 400 | `TIPO_ECF_REQUERIDO` | Falta `?tipo_ecf=` | Bug del cliente |
| 400 | `TIPO_ECF_INVALIDO` | Tipo fuera de `TIPOS_ECF` o no es entero | Bug del cliente |
| 403 | `SCOPE_INSUFICIENTE` | API-Key sin scope `pos:ready` | Rotar key con scope correcto |
| 401 | — | Sin auth / API-Key inválida / revocada / expirada / IP no autorizada | Reautenticar |
| 402 | `EMPRESA_INACTIVA` | `empresa.estado != ACTIVA` o `empresa.activa=False` | Bloquear POS; contactar admin |
| 402 | `SIN_SUSCRIPCION` | Empresa sin suscripción vigente (estado != ACTIVA o fuera de días de gracia) | Bloquear POS; contactar admin |
| 402 | `SIN_PAQUETE` | No hay paquete activo | Bloquear POS |
| 402 | `PAQUETE_AGOTADO` | `PaqueteComprobantes.disponible == False` por agotamiento | Bloquear POS; solicitar paquete |
| 403 | `RANGO_EXCEDE_PLAN` | Rango solicitado excede el límite del plan | Realizar upgrade |
| 403 | `SCOPE_INSUFICIENTE` | API-Key sin scope `pos:ready` | Rotar key con scope correcto |
| 404 | `SIN_SECUENCIAL` | No hay rango configurado para ese tipo | Configurar secuencial |
| 404 | `SECUENCIAL_BLOQUEADO` | `Secuencial.bloqueado=True` | Mostrar motivo al cajero |
| 404 | `SECUENCIAL_AGOTADO` | `ultimo_numero >= maximo_asignado` | Solicitar nuevo rango a DGII |
| 412 | `SIN_CERTIFICADO` | No hay `CertificadoDigital` activo | Subir certificado (.p12) desde el POS |
| 412 | `CERTIFICADO_VENCIDO` | `cert.vigencia_hasta < hoy` | **BLOQUEANTE** (no se puede firmar) |
| 429 | `THROTTLE` | Excedió 60 req/min | Backoff exponencial |
| 500 | `ERROR_INTERNO` | Excepción no controlada en `validar_pos_ready` | Reintentar en 30s |

---

## 🧮 Lógica del validator

### `apps/pos/services.py::validar_pos_ready`

```python
"""
apps/pos/services.py

Lógica de validación pre-emisión. Pura, sin DRF, fácil de testear.
    Retorna dict con: {status: int, code?: str, detail?: str, puede_emitir?: bool, certificado?: dict,
    alertas_secuenciales?: list, validado_en?: str}.
"""
import logging
from typing import TypedDict
from django.utils import timezone
from empresas.models import Empresa, CertificadoDigital
from sequences.models import Secuencial, TIPOS_ECF
from subscriptions.models import PaqueteComprobantes

logger = logging.getLogger(__name__)


class ValidationResult(TypedDict, total=False):
    status: int
    code: str
    detail: str
    puede_emitir: bool
    certificado: dict
    alertas_secuenciales: list
    validado_en: str


# Umbrales
PCT_SECUENCIAL_CRITICO = 10  # alerta si queda <= 10% del rango


def validar_pos_ready(empresa: Empresa, tipo_ecf: int) -> ValidationResult:
    """
    Valida si la empresa puede emitir un e-CF del tipo dado.
    NO lanza excepciones; convierte cada fallo en un dict estructurado.
    """
    alertas_secuenciales: list = []

    # ─── 1. Validar tipo_ecf ──────────────────────────────────────────────
    if tipo_ecf not in TIPOS_ECF:
        return {
            "status": 400,
            "code": "TIPO_ECF_INVALIDO",
            "detail": f"Tipo e-CF {tipo_ecf} no válido. Permitidos: {sorted(TIPOS_ECF.keys())}",
        }

    # ─── 2. Empresa activa (multi-tenant defensivo) ──────────────────────
    if not empresa.activa or empresa.estado != Empresa.ESTADO_ACTIVA:
        return {
            "status": 402,
            "code": "EMPRESA_INACTIVA",
            "detail": f"Empresa en estado {empresa.estado} (activa={empresa.activa}).",
        }

    # ─── 3. Suscripción activa (usar property esta_activa) ───────────────
    suscripcion = next(
        (s for s in empresa.suscripciones.all() if s.esta_activa),
        None,
    )
    if not suscripcion:
        return {
            "status": 402,
            "code": "SIN_SUSCRIPCION",
            "detail": "No hay suscripción activa o está fuera del período de gracia.",
        }

    # ─── 4. Paquete con comprobantes disponibles (usar property disponible) ──
    paquete = next(
        (p for p in empresa.paquetes.all() if p.disponible),
        None,
    )
    if not paquete:
        # Diagnosticar razón específica
        paquetes = list(empresa.paquetes.all())
        if not paquetes:
            return {
                "status": 402,
                "code": "SIN_PAQUETE",
                "detail": "La empresa no tiene paquetes de comprobantes.",
            }
        # Hay paquetes pero ninguno disponible
        estados = ", ".join(f"{p.estado}" for p in paquetes)
        return {
            "status": 402,
            "code": "PAQUETE_AGOTADO",
            "detail": f"Hay {len(paquetes)} paquete(s) pero ninguno disponible. Estados: {estados}.",
        }

    # ─── 5. Secuencial ───────────────────────────────────────────────────
    try:
        secuencial = Secuencial.objects.get(empresa=empresa, tipo_ecf=tipo_ecf)
    except Secuencial.DoesNotExist:
        return {
            "status": 404,
            "code": "SIN_SECUENCIAL",
            "detail": f"No hay secuencial configurado para el tipo e-CF {tipo_ecf}.",
        }

    if secuencial.bloqueado:
        return {
            "status": 404,
            "code": "SECUENCIAL_BLOQUEADO",
            "detail": f"Secuencial bloqueado. Motivo: {secuencial.motivo_bloqueo or 'no especificado'}.",
        }

    if secuencial.ultimo_numero >= secuencial.maximo_asignado:
        return {
            "status": 404,
            "code": "SECUENCIAL_AGOTADO",
            "detail": f"Secuencial agotado ({secuencial.ultimo_numero}/{secuencial.maximo_asignado}).",
        }

    # ─── 6. Certificado activo y vigente ─────────────────────────────────
    cert = empresa.certificados.filter(activo=True).order_by("-creado_at").first()
    if not cert:
        return {
            "status": 412,
            "code": "SIN_CERTIFICADO",
            "detail": "No hay certificado digital activo.",
        }

    hoy = timezone.now().date()
    dias_cert = (cert.vigencia_hasta - hoy).days

    if cert.vigencia_hasta < hoy:
        return {
        "status": 412,
        "code": "CERTIFICADO_VENCIDO",
        "detail": f"Certificado vencido hace {abs(dias_cert)} días ({cert.vigencia_hasta.isoformat()}).",
    }

    # ─── 7. Alertas (no bloquean) ────────────────────────────────────────
    # Alerta: secuencial próximo a agotarse
    rango = secuencial.maximo_asignado - secuencial.minimo_asignado + 1
    usados = secuencial.ultimo_numero - secuencial.minimo_asignado + 1
    restantes = max(0, rango - usados)
    if rango > 0:
        pct_restante = (restantes / rango) * 100
        if pct_restante <= PCT_SECUENCIAL_CRITICO:
            alertas_secuenciales.append({
                "tipo_ecf": secuencial.tipo_ecf,
                "disponibles": restantes,
                "alerta": "CRÍTICO: Secuenciales próximos a agotarse",
            })

    return {
        "status": 200,
        "puede_emitir": True,
        "certificado": {
            "estatus": "valido",
            "dias_restantes": dias_cert,
        },
        "alertas_secuenciales": alertas_secuenciales,
        "validado_en": timezone.now().isoformat(),
    }
```

### `apps/pos/views.py::PosReadyView`

```python
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status

from empresas.models import Empresa
from sequences.models import TIPOS_ECF
from .permissions import IsPosOnly, HasPosReadyScope
from .throttles import PosReadyThrottle
from .services import validar_pos_ready

logger = logging.getLogger(__name__)


class PosReadyView(APIView):
    permission_classes = [IsPosOnly, HasPosReadyScope]
    throttle_classes = [PosReadyThrottle]

    def get(self, request):
        tipo_ecf_raw = request.query_params.get("tipo_ecf")
        if tipo_ecf_raw is None:
            return Response(
                {"detail": "Parámetro 'tipo_ecf' es requerido.", "code": "TIPO_ECF_REQUERIDO"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        try:
            tipo_ecf = int(tipo_ecf_raw)
        except (ValueError, TypeError):
            return Response(
                {"detail": "tipo_ecf debe ser un entero.", "code": "TIPO_ECF_INVALIDO"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

    # Resolver empresa según el tipo de auth
    user = request.user
    if isinstance(user, Empresa) or hasattr(user, "rnc"):
        empresa = user
    else:
        # IsPosOnly ya bloqueó este caso, pero defensivo
        return Response(
            {"detail": "No se pudo resolver la empresa.", "code": "EMPRESA_INACTIVA"},
            status=http_status.HTTP_402_PAYMENT_REQUIRED,
        )

        # Llamar al service
        try:
            resultado = validar_pos_ready(empresa, tipo_ecf)
        except Exception as exc:
            logger.exception(f"pos_ready_error empresa={empresa.rnc} tipo_ecf={tipo_ecf} error={exc}")
            return Response(
                {"detail": "Error interno al validar.", "code": "ERROR_INTERNO"},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        status_code = resultado.pop("status")

        # Log de auditoría para 4xx (monitoreo de seguridad)
        if 400 <= status_code < 500 and status_code not in (400,):
            logger.warning(
                f"pos_ready_4xx empresa={empresa.rnc} tipo_ecf={tipo_ecf} "
                f"code={resultado.get('code')} status={status_code} "
                f"ip={request.META.get('REMOTE_ADDR')}"
            )

        return Response(resultado, status=status_code)
```

### `apps/pos/urls.py`

```python
from django.urls import path
from .views import PosReadyView

app_name = "pos"

urlpatterns = [
    path("pos/ready/", PosReadyView.as_view(), name="pos-ready"),
]
```

### Registro en `core/urls.py`

```python
# core/urls.py (bajo urlpatterns de api/v1/)
path("api/v1/", include("apps.pos.urls")),
```

### `INSTALLED_APPS` en `core/settings/base.py`

```python
INSTALLED_APPS = [
    # ... existing apps ...
    "apps.pos",  # o solo "pos" según configuración
]
```

> **Nota:** Verificar cómo está registrado el resto. Si usan `name = "empresas"` (sin prefijo apps.), usar `"pos"`. Si usan `"apps.empresas"`, usar `"apps.pos"`. Confirmar con `core/settings/base.py:69-79` actual que ya tiene `'empresas'`, `'subscriptions'`, etc. (sin prefijo `apps.`).

### `apps/api_keys/models.py` (modificación)

Agregar `"pos:ready"` a `SCOPES_VALIDOS`:

```python
class ApiKey(models.Model):
    SCOPES_VALIDOS = [
        "comprobantes:crear",
        "comprobantes:consultar",
        "comprobantes:anular",
        "secuenciales:consultar",
        "pos:ready",  # NUEVO
    ]
    # ... resto sin cambios ...
```

---

## 🧪 Tests

### `apps/pos/tests.py` — Tests del service (unitarios, sin DRF)

| # | Test | Esperado |
|---|------|----------|
| S1 | `test_service_empresa_inactiva` | 402 + `EMPRESA_INACTIVA` |
| S2 | `test_service_sin_suscripcion` | 402 + `SIN_SUSCRIPCION` |
| S3 | `test_service_suscripcion_suspendida` | 402 + `SIN_SUSCRIPCION` |
| S4 | `test_service_suscripcion_vencida_en_gracia` | 200 (si `plan.dias_gracia > 0` y dentro de la ventana) |
| S5 | `test_service_sin_paquete` | 402 + `SIN_PAQUETE` |
| S6 | `test_service_paquete_agotado` | 402 + `PAQUETE_AGOTADO` |
| S7 | `test_service_paquete_vencido` | 402 + `PAQUETE_AGOTADO` (porque `disponible=False`) |
| S8 | `test_service_sin_secuencial` | 404 + `SIN_SECUENCIAL` |
| S9 | `test_service_secuencial_bloqueado` | 404 + `SECUENCIAL_BLOQUEADO` |
| S10 | `test_service_secuencial_agotado` | 404 + `SECUENCIAL_AGOTADO` |
| S11 | `test_service_sin_certificado` | 412 + `SIN_CERTIFICADO` |
| S12 | `test_service_cert_vencido` | 412 + `CERTIFICADO_VENCIDO` |
| S13 | `test_service_todo_ok_sin_alertas` | 200 + `puede_emitir=True` + `alertas_secuenciales=[]` |
| S14 | `test_service_secuencial_critico_warn` | 200 + `alertas_secuenciales` con alerta crítica |
| S15 | `test_service_tipo_ecf_invalido` | 400 + `TIPO_ECF_INVALIDO` |

### `apps/pos/tests.py` — Tests de la view (integración con DRF)

| # | Test | Esperado |
|---|------|----------|
| V1 | `test_view_todo_ok_api_key` | 200 + `puede_emitir=true` + `certificado` |
| V2 | `test_view_sin_auth` | 401 |
| V3 | `test_view_sin_tipo_ecf` | 400 + `TIPO_ECF_REQUERIDO` |
| V4 | `test_view_tipo_ecf_no_entero` | 400 + `TIPO_ECF_INVALIDO` |
| V5 | `test_view_tipo_ecf_fuera_de_tipos` | 400 + `TIPO_ECF_INVALIDO` |
| V6 | `test_view_api_key_sin_scope_pos_ready` | 403 + `SCOPE_INSUFICIENTE` |
| V7 | `test_view_api_key_otra_empresa_no_ve_datos` | Empresa A con key A no ve datos de empresa B (test multi-tenant real) |
| V8 | `test_view_throttle_excedido` | 61ª request en 1 min → 429 |
| V9 | `test_view_empresa_suspendida` | 402 + `EMPRESA_INACTIVA` |
| V10 | `test_view_api_key_expirada` | 401 (ApiKey.verificar retorna None) |
| V11 | `test_view_api_key_revocada` | 401 |

### `apps/sequences/tests.py` (12 tests)

| # | Test | Esperado |
|---|------|----------|
| 1 | `test_api_key_puede_crear_secuencial` | 201 |
| 2 | `test_api_key_puede_actualizar_secuencial` | 200 |
| 3 | `test_api_key_no_puede_listar_secuenciales` | 403 |
| 4 | `test_api_key_no_puede_retrieve_secuencial` | 403 |
| 5 | `test_api_key_no_puede_preview_secuencial` | 403 |
| 6 | `test_api_key_no_puede_eliminar_secuencial` | 403 |
| 7 | `test_api_key_no_puede_bloquear_secuencial` | 403 |
| 8 | `test_api_key_no_puede_desbloquear_secuencial` | 403 |
| 9 | `test_api_key_no_puede_ver_secuencial_otra_empresa` | 403 |
| 10 | `test_superadmin_puede_listar_secuenciales` | 200 |
| 11 | `test_superadmin_puede_bloquear_secuencial` | 200 |
| 12 | `test_superadmin_puede_desbloquear_secuencial` | 200 |

**Total: ~39 tests nuevos (15 service + 12 view + 12 secuenciales).**

### Setup necesario en tests

```python
# apps/pos/tests.py
import tempfile
from datetime import date, timedelta
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase
from unittest.mock import patch

from empresas.models import Empresa, CertificadoDigital
from empresas.crypto import cifrar
from subscriptions.models import Suscripcion, PaqueteComprobantes, Plan
from sequences.models import Secuencial
from api_keys.models import ApiKey
from users.models import Usuario
from .services import validar_pos_ready


def _make_empresa(rnc="131793916", estado=Empresa.ESTADO_ACTIVA, activa=True):
    return Empresa.objects.create(
        rnc=rnc, razon_social="Test SRL", ambiente=Empresa.AMBIENTE_TEST,
        estado=estado, activa=activa,
    )


def _make_plan(nombre="Plan Test", limite=1000, tipos=None, dias_gracia=0):
    return Plan.objects.create(
        nombre=nombre, limite_comprobantes=limite,
        precio_mensual=100, precio_anual=1000,
        ciclo_disponible=Plan.CICLO_AMBOS, dias_gracia=dias_gracia,
        tipos_ecf_permitidos=tipos,  # None = todos
    )


def _make_suscripcion_activa(empresa, plan, fecha_renovacion=None):
    hoy = timezone.now().date()
    return Suscripcion.objects.create(
        empresa=empresa, plan=plan, ciclo=Suscripcion.CICLO_MENSUAL,
        estado=Suscripcion.ESTADO_ACTIVA,
        fecha_inicio=hoy - timedelta(days=15),
        fecha_renovacion=fecha_renovacion or (hoy + timedelta(days=15)),
    )


def _make_paquete_disponible(empresa, suscripcion, plan, total=1000, usados=0, fecha_vencimiento=None):
    return PaqueteComprobantes.objects.create(
        empresa=empresa, suscripcion=suscripcion, plan=plan,
        total_comprobantes=total, comprobantes_usados=usados,
        estado=PaqueteComprobantes.ESTADO_ACTIVO,
        fecha_vencimiento=fecha_vencimiento or (timezone.now() + timedelta(days=30)),
    )


def _make_secuencial(empresa, tipo_ecf=31, bloqueado=False, ultimo_numero=0, maximo=9999999999):
    return Secuencial.objects.create(
        empresa=empresa, tipo_ecf=tipo_ecf,
        ultimo_numero=ultimo_numero, maximo_asignado=maximo,
        bloqueado=bloqueado,
    )


def _make_certificado(empresa, vigencia_hasta=None, activo=True):
    return CertificadoDigital.objects.create(
        empresa=empresa, alias="Test",
        archivo=SimpleUploadedFile("test.p12", b"fake-p12", content_type="application/x-pkcs12"),
        pin_cifrado=cifrar("1234"),
        vigencia_desde=date(2026, 1, 1),
        vigencia_hasta=vigencia_hasta or (date(2027, 1, 1)),
        activo=activo,
    )


def _make_api_key(empresa, scopes=None):
    key, token = ApiKey.crear(
        empresa=empresa, nombre="Test POS", creado_por=None,
        scopes=scopes or ["pos:ready"],
    )
    return key, token
```

---

## 🔧 Comandos para correr tests

```bash
# Solo POS (service + view)
python manage.py test apps.pos -v 2

# Solo Secuenciales
python manage.py test apps.sequences -v 2

# Ambos
python manage.py test apps.pos apps.sequences -v 2

# Solo el service (más rápido, sin DRF)
python manage.py test apps.pos.tests.PosReadyServiceTestCase -v 2
```

---

## ⚠️ Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| `apps/pos/` no detectada por Django | Agregar a `INSTALLED_APPS` Y a `core/urls.py` explícitamente |
| `IsPosOnly` rompe para Empresa sin `rol` | `Empresa.rol = None` ya existe en `apps/empresas/models.py:111`; usar `getattr` con default |
| Multi-tenant leak en `retrieve` (otra empresa) | `get_queryset()` filtra por `empresa_id` o `empresa=user`; DRF retorna 404 automático |
| `validar_pos_ready` no usa transacción | Es lectura pura; OK. Si se quisiera consistencia fuerte, envolver en `transaction.atomic()` con `select_for_update` en el paquete, pero el validator no debe bloquear |
| Tests del service sin DRF | `validar_pos_ready(empresa, tipo_ecf)` retorna dict, se testea sin `APIClient` |
| `makemigrations` se queja por `apps/pos/` sin migrations | Crear `apps/pos/migrations/__init__.py` vacío (es válido para apps sin modelos) |
| `Empresa.objects.get(pk=...)` puede retornar Empresa soft-deleted | Filtrar `deleted_at__isnull=True` en la view |
| Throttle cuenta requests fallidos también | Intencional: 401/403/402 también consumen cuota para evitar fuerza bruta |
| API-Key con scope `pos:ready` puede abusar de otros endpoints | `IsPosOnly` solo aplica a `pos/ready/`. Otros endpoints tienen sus propios permisos |
| DB caída durante `validar_pos_ready` | View envuelve en try/except → 500 `ERROR_INTERNO` (ver view arriba) |

---

## 📅 Plan de ejecución (orden de implementación)

1. **Refactor `apps/sequences/views.py`**: implementar permisos `IsPosApiKeyOnly` para create/update, `IsSuperAdminOnly` para el resto. Commit atómico.
2. **Crear `apps/sequences/tests.py`**: 12 tests de permisos. Verificar que pasan. Commit.
3. **Crear estructura `apps/pos/`**: `__init__.py`, `apps.py`, `migrations/__init__.py`. Commit.
4. **Crear `apps/pos/services.py`** con `validar_pos_ready()`. Commit.
5. **Crear `apps/pos/tests.py` — sección service**: 15 tests. Verificar. Commit.
6. **Crear `apps/pos/permissions.py`** con `IsPosOnly` + `HasPosReadyScope`. Commit.
7. **Crear `apps/pos/throttles.py`** con `PosReadyThrottle`. Commit.
8. **Crear `apps/pos/views.py`** con `PosReadyView`. Commit.
9. **Crear `apps/pos/urls.py`**. Commit.
10. **Registrar en `core/settings/base.py`**: `INSTALLED_APPS` + throttle rate `pos_ready`. Commit.
11. **Modificar `apps/api_keys/models.py`**: agregar `"pos:ready"` a `SCOPES_VALIDOS`. Generar migration. Commit.
12. **Registrar en `core/urls.py`**: `include("apps.pos.urls")`. Commit.
13. **Crear `apps/pos/tests.py` — sección view**: 12 tests de integración. Verificar. Commit.
14. **Actualizar `docs/integracion.md`**: sección 11.9 (permisos) + nueva sección 12 (pos/ready). Commit.
15. **Actualizar `docs/plan_fase2.md`**: insertar Hito 0.5 con link a este documento. Commit.
16. **Correr suite completa**: `python manage.py test apps.pos apps.sequences apps.api_keys -v 2`. Verificar 39/39.
17. **Push y verificar deploy** (cuando el usuario lo apruebe).

---

## ✅ Criterios de aceptación

1. **Permisos de `SecuencialViewSet`:**
   - API-Key puede hacer `POST /secuenciales/` y `PATCH /secuenciales/{id}/` (create/update rango).
   - API-Key recibe **403** al intentar `list`, `retrieve`, `preview`, `destroy`, `bloquear`, `desbloquear`.
   - JWT `SUPERADMIN` puede hacer todo sobre todas las empresas (`list`, `retrieve`, `preview`, `destroy`, `bloquear`, `desbloquear`).
   - API-Key de empresa A recibe **403** al pedir secuencial de empresa B (multi-tenant).

2. **`pos/ready/`:**
   - Retorna 200 con `{puede_emitir: true, certificado: {...}, alertas_secuenciales: [], validado_en: "..."}` cuando todo está OK.
   - Retorna 200 con `puede_emitir: true` + `alertas_secuenciales` cuando hay rangos críticos.
   - Retorna 4xx con `code` específico cuando falta suscripción, paquete, secuencial, certificado.
   - Retorna **412** `CERTIFICADO_VENCIDO` cuando `cert.vigencia_hasta < hoy` (bloqueante).
   - Retorna **402** `EMPRESA_INACTIVA` cuando `empresa.estado != ACTIVA` o `activa=False`.
   - Retorna **403** `SCOPE_INSUFICIENTE` cuando la API-Key no tiene `pos:ready`.
   - Retorna **429** al exceder 60 req/min.
   - Multi-tenant estricto: API-Key de empresa A solo ve datos de empresa A; API-Key de empresa A no puede usar `tipo_ecf` configurado solo en empresa B.
   - Log de auditoría para todas las respuestas 4xx (excepto 400 input inválido).

3. **Documentación:**
   - `docs/integracion.md` sección 11.9 actualizada con permisos correctos.
   - `docs/integracion.md` nueva sección 12 con `pos/ready/` (formato, response, errores).
   - `docs/plan_fase2.md` con Hito 0.5 marcado y link a este documento.

4. **Tests:**
   - 15 tests del service + 12 tests de la view + 12 tests de secuenciales = 39 nuevos pasan.
   - Cero regresiones en tests existentes.

5. **No se toca:**
   - Lógica de firma de XMLs (sigue server-side en Hito 3).
   - Snapshot pesado (vive en `plan_webhook_snapshot.md`).
   - CRUD de comprobantes (Hito 1).
   - Modelos `Suscripcion` / `PaqueteComprobantes` / `Empresa` (se usan sus properties ya existentes).

---

## 🔗 Referencias cruzadas

- [`plan_fase2.md`](./plan_fase2.md) — Plan maestro Fase 2 (Hito 0.5 referenciado aquí)
- [`plan_webhook_snapshot.md`](./plan_webhook_snapshot.md) — Webhook `empresa.snapshot` (Hito 0.6)
- `docs/integracion.md` — Documentación de integración con el POS
- `apps/sequences/models.py` — Modelo `Secuencial` y `TIPOS_ECF`
- `apps/pos/permissions.py` — `IsPosOnly`, `IsPosApiKeyOnly`, `IsSuperAdminOnly`, `HasPosReadyScope`
- `apps/sequences/permissions.py` — `IsSuperAdminOnly` (reemplaza a los anteriores permisos)
- `apps/empresas/models.py` — `Empresa` (incluye `is_authenticated`, `rol = None`, `estado`, `activa`)
- `apps/api_keys/authentication.py` — `ApiKeyAuthentication` (setea `request.user = Empresa`, `request.auth = ApiKey`)
- `apps/subscriptions/models.py` — `Suscripcion.esta_activa`, `PaqueteComprobantes.disponible`, `PaqueteComprobantes.comprobantes_restantes`
- `apps/empresas/models.py:172-201` — `CertificadoDigital` (campos `vigencia_desde`, `vigencia_hasta`, `activo`)

---

## 🚦 Estado

- [x] Plan completo y aprobado
- [ ] Refactor `apps/sequences/views.py` (permisos)
- [ ] Tests `apps/sequences/tests.py` (12 tests)
- [ ] Estructura `apps/pos/` (`__init__.py`, `apps.py`, `migrations/`)
- [ ] `apps/pos/services.py` con `validar_pos_ready()`
- [ ] Tests del service (15 tests)
- [ ] `apps/pos/permissions.py` (`IsPosOnly`, `HasPosReadyScope`, `IsPosApiKeyOnly`, `IsSuperAdminOnly`)
- [ ] `apps/pos/throttles.py` (`PosReadyThrottle`)
- [ ] `apps/pos/views.py` (`PosReadyView`)
- [ ] `apps/pos/urls.py`
- [ ] `INSTALLED_APPS` + throttle rate en `base.py`
- [ ] `apps/api_keys/models.py` + scope `"pos:ready"` + migration
- [ ] `core/urls.py` include
- [ ] Tests de la view (12 tests)
- [ ] `docs/integracion.md` actualizado
- [ ] `docs/plan_fase2.md` actualizado
- [ ] Suite completa pasa (39/39)
- [ ] Push a repo + deploy verificado
