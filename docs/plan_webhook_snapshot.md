# Plan: Webhook `empresa.snapshot`

> **Contexto general:** Ver [`plan_fase2.md`](./plan_fase2.md) — **Hito 0.6 — Webhook Snapshot (prerrequisito del Hito 1)**.
> **Documento hermano:** [`plan_secuenciales_refactor.md`](./plan_secuenciales_refactor.md) — POS-Ready validator ligero (pull antes de cada emisión).
>
> **Principio de diseño:** El POS cachea localmente el snapshot pesado que recibe por webhook. Antes de cada emisión valida con `pos/ready/` (validator ligero) sin descargar todo el payload. Esta separación evita overhead en cada comprobante y entrega datos proactivos (alertas, vigencias) sin polling.

---

## 🎯 Objetivo

1. Enviar al POS (vía webhook firmado) **TODA la información de la empresa** cada día a las **06:00 AM** (Celery Beat).
2. También disparar el snapshot en **cambios importantes**: suscripción, paquete, secuencial, certificado.
3. Firmar cada delivery con **HMAC-SHA256** usando un `webhook_secret` dedicado generado al crear la API-Key.
4. Implementar un **dispatcher mínimo temporal** (reemplazable en Hito 4 con retry exponencial, DLQ, métricas, UI).
5. Reusar la infraestructura de webhooks existente cuando esté lista (Hito 4); hasta entonces, dispatcher aislado.

---

## 🏗️ Alcance

- `armar_snapshot_empresa(empresa)` — función pura que arma el payload pesado.
- `dispatcher_webhook_minimo()` — función que hace POST al POS con firma HMAC.
- `enviar_snapshot_empresa(empresa_id)` — task Celery que arma + dispatcha.
- `enviar_snapshot_diario()` — task Celery Beat que recorre todas las empresas activas.
- `apps/empresas/signals.py` — `post_save` en Suscripcion, PaqueteComprobantes, Secuencial, CertificadoDigital.
- `apps/empresas/tasks.py` — registro de tasks con `@shared_task`.
- `CELERY_BEAT_SCHEDULE` en `core/settings/base.py` con cron `0 6 * * *`.
- Nuevo campo `webhook_secret_cifrado` en `ApiKey` (cifrado con Fernet).

---

## ❌ Fuera de alcance

- CRUD de webhooks (Hito 4 de Fase 2, Bloque 3).
- Reintentos con backoff exponencial + DLQ (Hito 4).
- UI de gestión de webhooks (Hito 4).
- Snapshot por cambio de `Comprobante` (eso lo dispara Bloque 3 con `comprobante.aceptado`).
- Snapshot por cambio de `Usuario` o `Cliente`.

---

## 🔐 Decisión de diseño: HMAC con `webhook_secret` dedicado

**Problema:** `ApiKey.key_hash` (apps/api_keys/models.py:68) es solo el SHA-256 del token. El token original **no se guarda** post-creación (`apps/api_keys/models.py:147-167` lo descarta tras calcular el hash). Por tanto, el dispatcher no puede firmar con `api_key.token.encode()`.

**Opciones consideradas:**

| Opción | Pros | Contras |
|--------|------|---------|
| (a) Reusar `api_key.token` como HMAC secret | Simple, sin nuevos campos | Token no se guarda; imposible firmar sin pedirlo al POS cada vez |
| (b) Generar `webhook_secret` separado al crear la API-Key y devolverlo una vez al cliente | Mismo flujo que `secret` de Webhook, aislado del token de auth | El POS debe guardar 2 secretos |
| (c) Cifrar el `api_key.token` con Fernet y guardarlo en `ApiKey` | Reusa token, no requiere nuevo secreto | Mezcla concerns (auth + firma) |
| (d) Pre-shared salt en `.env` | Mínimo cambio | Mismo secret para todos los POS, no se puede revocar individualmente |

**Decisión: Opción (b)** — generar `webhook_secret` (32 bytes, base64-url) al crear la API-Key, cifrarlo con Fernet y guardarlo en `ApiKey.webhook_secret_cifrado`. Devolverlo **una sola vez** en el `POST /api-keys/` (igual que el `token`).

**Flujo:**

```
1. Admin crea API-Key vía POST /api-keys/
2. Backend genera:
   - token (RNC_aleatorio, se muestra una vez, NO se guarda)
   - webhook_secret (32 bytes base64-url, se muestra una vez, se guarda CIFRADO)
3. Response 201:
   {
     "id": "...",
     "nombre": "POS Sucursal Norte",
     "token": "131793916_xxxxx",         # solo esta vez
     "webhook_secret": "aB3dEf...==",    # solo esta vez
     "scopes": ["comprobantes:crear", "pos:ready"],
     ...
   }
4. POS guarda ambos secretos localmente:
   - token → para Authorization: Api-Key
   - webhook_secret → para verificar X-Webhook-Signature en webhooks entrantes
5. Backend firma el snapshot con HMAC-SHA256(webhook_secret, body)
6. POS verifica: hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
```

**Migración:** Se agrega `webhook_secret_cifrado` a `ApiKey` con default `""`. Las API-Keys existentes se quedan sin webhook secret (no firman; en Hito 4 se regenerará). Para esta fase, solo API-Keys nuevas tienen secret.

---

## 📁 Archivos

### Nuevos

| Archivo | Contenido |
|---------|-----------|
| `apps/empresas/services.py` | `armar_snapshot_empresa(empresa)`, helpers `_serializar_*`, `dispatcher_webhook_minimo()` |
| `apps/empresas/tasks.py` | `enviar_snapshot_empresa(empresa_id)`, `enviar_snapshot_diario()` |
| `apps/empresas/signals.py` | `post_save` en Suscripcion, PaqueteComprobantes, Secuencial, CertificadoDigital |

### Modificados

| Archivo | Cambio |
|---------|--------|
| `apps/api_keys/models.py` | Agregar `webhook_secret_cifrado = TextField(blank=True)`. Generar `webhook_secret` en `ApiKey.crear()` y devolverlo. Agregar `obtener_webhook_secret()` que descifra con Fernet. |
| `apps/api_keys/serializers.py` | Exponer `webhook_secret` solo en `create()`, igual que `token` |
| `apps/api_keys/views.py` | Devolver `webhook_secret` en el response de creación (junto al `token`) |
| `apps/api_keys/migrations/0004_*.py` | Migration nueva para el campo |
| `apps/empresas/apps.py` | `ready()` importa `signals` (los conecta) |
| `apps/empresas/tests.py` | +14 tests de snapshot + dispatcher + signals + secret generation |
| `core/settings/base.py` | `CELERY_BEAT_SCHEDULE['enviar-snapshot-diario']` con cron `0 6 * * *` |
| `docs/integracion.md` | Nueva sección 13 con evento `empresa.snapshot` (payload, headers, triggers, secret management) |
| `docs/plan_fase2.md` | Insertar **Hito 0.6 — Webhook Snapshot** antes del Hito 1 |

---

## ⏰ Triggers del snapshot

| Trigger | Cuándo se dispara | Task Celery |
|---------|-------------------|-------------|
| **Diario 06:00 AM** | Celery Beat (`0 6 * * *`) | `enviar_snapshot_diario()` |
| Cambio de suscripción | `post_save` Suscripcion | `enviar_snapshot_empresa(empresa_id)` |
| Cambio de paquete | `post_save` PaqueteComprobantes | `enviar_snapshot_empresa(empresa_id)` |
| Cambio de secuencial | `post_save` Secuencial | `enviar_snapshot_empresa(empresa_id)` |
| Cambio de certificado | `post_save` CertificadoDigital | `enviar_snapshot_empresa(empresa_id)` |

### ¿Por qué no trigger en `Comprobante`?

- El estado de un comprobante cambia constantemente durante la emisión.
- El snapshot es para **información estructural de la empresa**, no transaccional.
- Los eventos de comprobantes (`comprobante.aceptado`, `comprobante.rechazado`) los maneja el Bloque 3 con su propio sistema.

---

## 📬 Payload del evento `empresa.snapshot`

### Estructura

```json
{
  "evento": "empresa.snapshot",
  "version": 1,
  "enviado_en": "2026-06-01T06:00:00Z",
  "empresa": {
    "id": "<uuid>",
    "rnc": "131793916",
    "razon_social": "Empresa Demo SRL",
    "nombre_comercial": "Demo POS",
    "ambiente": "testecf",
    "estado": "ACTIVA",
    "activa": true
  },
  "suscripcion": {
    "id": "<uuid>",
    "estado": "ACTIVA",
    "plan": {
      "id": "<uuid>",
      "nombre": "Plan Inicial",
      "limite_comprobantes": 1000,
      "tipos_ecf_permitidos": [31, 32, 41]
    },
    "fecha_inicio": "2026-05-01",
    "fecha_renovacion": "2026-07-01",
    "dias_para_vencer": 30
  },
  "paquete": {
    "id": "<uuid>",
    "total_comprobantes": 1000,
    "comprobantes_usados": 150,
    "comprobantes_disponibles": 850,
    "porcentaje_restante": 85.0,
    "estado": "ACTIVO",
    "fecha_vencimiento": "2026-07-01T23:59:59Z"
  },
  "secuencial": {
    "tipo_ecf": 31,
    "proximo_encf": "E310000151",
    "ultimo_numero": 150,
    "maximo_asignado": 9999999999,
    "porcentaje_uso": 0.0015,
    "casi_agotado": false,
    "bloqueado": false
  },
  "certificado": {
    "id": "<uuid>",
    "alias": "Cert. Principal",
    "activo": true,
    "vigencia_desde": "2026-01-15",
    "vigencia_hasta": "2027-01-15",
    "dias_para_vencer": 260,
    "vence_pronto": false,
    "hash_sha256": "abc123def456..."
  },
  "alertas": []
}
```

### Con alertas (mismo payload + `alertas` no vacío)

```json
{
  "alertas": [
    {
      "codigo": "COMPROBANTES_BAJOS",
      "severidad": "WARN",
      "mensaje": "Quedan 50 comprobantes disponibles (5%)."
    },
    {
      "codigo": "CERT_VENCE_PRONTO",
      "severidad": "WARN",
      "mensaje": "El certificado vence en 25 días."
    },
    {
      "codigo": "PAQUETE_POR_VENCER",
      "severidad": "WARN",
      "mensaje": "El paquete vence en 5 días."
    }
  ]
}
```

> **Nota sobre `secuencial`:** El snapshot incluye un solo secuencial (el primero ordenado por `tipo_ecf`). En Hito futuro se puede expandir a todos los tipos si el POS lo necesita. Para tener `secuencial` por tipo, el POS debe llamar `GET /api/v1/secuenciales/?tipo_ecf=N` (refactor Hito 0.5).

---

## 📨 Headers HTTP del webhook

| Header | Valor | Ejemplo |
|--------|-------|---------|
| `Content-Type` | `application/json` | `application/json` |
| `X-Webhook-Event` | Nombre del evento | `empresa.snapshot` |
| `X-Webhook-Delivery` | UUID único por delivery (idempotencia) | `7f9c4e2a-1234-5678-9abc-def012345678` |
| `X-Webhook-Signature` | HMAC-SHA256 del body | `sha256=a1b2c3d4...` |
| `User-Agent` | Identificador del sender | `DerejFactAPI-Webhooks/1.0` |

### Formato de la firma

```
X-Webhook-Signature: sha256=<hex_digest>
```

Donde:
```
hex_digest = HMAC-SHA256(secret=webhook_secret, message=raw_body)
```

El POS verifica:
```python
expected = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected, signature.split("=", 1)[1]):
    return 401
```

---

## 🔧 Implementación

### `apps/api_keys/models.py` (modificación)

```python
import secrets
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from empresas.crypto import cifrar, descifrar  # ya existe en apps/empresas/crypto.py


class ApiKey(models.Model):
    # ... existing fields ...
    # CAMPO NUEVO:
    webhook_secret_cifrado = models.TextField(
        blank=True, default="",
        help_text="Secret para HMAC de webhooks, cifrado con Fernet. Se muestra una sola vez al crear.",
    )

    SCOPES_VALIDOS = [
        "comprobantes:crear",
        "comprobantes:consultar",
        "comprobantes:anular",
        "secuenciales:consultar",
        "pos:ready",
    ]
    # ... resto del modelo sin cambios ...

    @classmethod
    def crear(cls, empresa, nombre, creado_por, scopes=None, allowed_ips=None,
              rate_limit_cantidad=100, rate_limit_ventana=VENTANA_HORA, expira_at=None,
              generar_webhook_secret=True):
        """
        Crea una nueva API key.
        Retorna (instancia, token_completo, webhook_secret_o_None).
        Ambos secretos se muestran UNA VEZ al usuario.
        """
        # ... validaciones existentes (límite, etc.) ...

        rnc_limpio = empresa.rnc.replace('-', '')
        token_aleatorio = secrets.token_urlsafe(32)
        token = f"{rnc_limpio}_{token_aleatorio}"
        prefix = rnc_limpio
        key_hash = hashlib.sha256(token.encode()).hexdigest()

        # Generar webhook_secret si está habilitado
        webhook_secret = None
        webhook_secret_cifrado = ""
        if generar_webhook_secret:
            webhook_secret = secrets.token_urlsafe(32)
            webhook_secret_cifrado = cifrar(webhook_secret)

        instancia = cls(
            empresa=empresa,
            nombre=nombre,
            creado_por=creado_por,
            prefix=prefix,
            key_hash=key_hash,
            scopes=scopes or [],
            allowed_ips=allowed_ips or [],
            rate_limit_cantidad=rate_limit_cantidad,
            rate_limit_ventana=rate_limit_ventana,
            expira_at=expira_at,
            webhook_secret_cifrado=webhook_secret_cifrado,
        )
        instancia.full_clean()
        instancia.save()
        return instancia, token, webhook_secret

    def obtener_webhook_secret(self) -> str | None:
        """Descifra y retorna el webhook_secret. None si no tiene (key antigua)."""
        if not self.webhook_secret_cifrado:
            return None
        return descifrar(self.webhook_secret_cifrado)
```

> **Breaking change:** `ApiKey.crear()` ahora retorna 3 valores en vez de 2. Hay que actualizar todos los call sites: tests en `apps/api_keys/tests.py` y `apps/pos/tests.py`. Verificar también `apps/api_keys/views.py::create()` que use los 3.

### `apps/api_keys/serializers.py` (modificación)

```python
class ApiKeySerializer(serializers.ModelSerializer):
    # Campos write-only que solo se devuelven en create()
    token = serializers.CharField(read_only=True, required=False)
    webhook_secret = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = ApiKey
        fields = [
            'id', 'empresa', 'nombre', 'prefix', 'scopes', 'allowed_ips',
            'rate_limit_cantidad', 'rate_limit_ventana', 'activa', 'expira_at',
            'ultimo_uso_at', 'ultimo_uso_ip', 'creado_at', 'actualizado_at',
            'token', 'webhook_secret',
        ]
        read_only_fields = [
            'id', 'prefix', 'ultimo_uso_at', 'ultimo_uso_ip',
            'creado_at', 'actualizado_at', 'token', 'webhook_secret',
        ]
```

### `apps/api_keys/views.py` (modificación)

```python
def create(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    empresa = serializer.validated_data['empresa']
    api_key, token, webhook_secret = ApiKey.crear(
        empresa=empresa,
        nombre=serializer.validated_data['nombre'],
        creado_por=request.user if isinstance(request.user, Usuario) else None,
        scopes=serializer.validated_data.get('scopes', []),
        allowed_ips=serializer.validated_data.get('allowed_ips', []),
        rate_limit_cantidad=serializer.validated_data.get('rate_limit_cantidad', 100),
        rate_limit_ventana=serializer.validated_data.get('rate_limit_ventana', ApiKey.VENTANA_HORA),
        expira_at=serializer.validated_data.get('expira_at'),
    )
    data = ApiKeySerializer(api_key).data
    data['token'] = token  # solo esta vez
    if webhook_secret:
        data['webhook_secret'] = webhook_secret  # solo esta vez
    return Response(data, status=status.HTTP_201_CREATED)
```

> **Importante:** `webhook_secret` se retorna **UNA VEZ** en `POST /api-keys/`. Nunca en `GET`, `PATCH`, ni `LIST`. El serializer ya lo tiene como `read_only`, no se persiste en el response de detalle.

### `apps/empresas/services.py` (nuevo)

```python
"""
apps/empresas/services.py

Servicios relacionados con Empresa:
- armar_snapshot_empresa(): arma el payload pesado para webhook
- dispatcher_webhook_minimo(): POST al POS con firma HMAC-SHA256
"""
import hashlib
import hmac
import json
import logging
import os
import uuid
from typing import Optional

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Umbrales (alineados con apps.pos.services) ────────────────────────
PCT_COMPROBANTES_BAJOS = 10
DIAS_CERT_VENCE_PRONTO = 30
DIAS_PAQUETE_POR_VENCER = 7
DIAS_SUSCRIPCION_POR_VENCER = 7


def _serializar_suscripcion(suscripcion) -> Optional[dict]:
    if not suscripcion:
        return None
    plan = suscripcion.plan
    dias = None
    if suscripcion.fecha_renovacion:
        dias = (suscripcion.fecha_renovacion - timezone.now().date()).days
    return {
        "id": str(suscripcion.id),
        "estado": suscripcion.estado,
        "esta_activa": suscripcion.esta_activa,  # usa la property
        "plan": {
            "id": str(plan.id),
            "nombre": plan.nombre,
            "limite_comprobantes": plan.limite_comprobantes,
            "tipos_ecf_permitidos": plan.tipos_ecf_permitidos,
        },
        "fecha_inicio": suscripcion.fecha_inicio.isoformat() if suscripcion.fecha_inicio else None,
        "fecha_renovacion": suscripcion.fecha_renovacion.isoformat() if suscripcion.fecha_renovacion else None,
        "dias_para_vencer": dias,
    }


def _serializar_paquete(paquete) -> Optional[dict]:
    if not paquete:
        return None
    disponibles = paquete.comprobantes_restantes  # usa la property
    pct = (disponibles / paquete.total_comprobantes) * 100 if paquete.total_comprobantes else 0
    return {
        "id": str(paquete.id),
        "total_comprobantes": paquete.total_comprobantes,
        "comprobantes_usados": paquete.comprobantes_usados,
        "comprobantes_disponibles": disponibles,
        "porcentaje_restante": round(pct, 2),
        "estado": paquete.estado,
        "disponible": paquete.disponible,  # usa la property
        "fecha_vencimiento": paquete.fecha_vencimiento.isoformat() if paquete.fecha_vencimiento else None,
    }


def _serializar_certificado(cert) -> Optional[dict]:
    if not cert:
        return None
    dias = (cert.vigencia_hasta - timezone.now().date()).days
    hash_sha256 = None
    if cert.archivo:
        try:
            with open(cert.archivo.path, "rb") as f:
                hash_sha256 = hashlib.sha256(f.read()).hexdigest()
        except (FileNotFoundError, ValueError, OSError):
            pass
    return {
        "id": str(cert.id),
        "alias": cert.alias,
        "activo": cert.activo,
        "vigencia_desde": cert.vigencia_desde.isoformat(),
        "vigencia_hasta": cert.vigencia_hasta.isoformat(),
        "dias_para_vencer": dias,
        "vence_pronto": 0 < dias <= DIAS_CERT_VENCE_PRONTO,
        "hash_sha256": hash_sha256,
    }


def _serializar_secuencial(secuencial) -> Optional[dict]:
    if not secuencial:
        return None
    return {
        "tipo_ecf": secuencial.tipo_ecf,
        "proximo_encf": secuencial.proximo_encf(),
        "ultimo_numero": secuencial.ultimo_numero,
        "maximo_asignado": secuencial.maximo_asignado,
        "porcentaje_uso": round(secuencial.porcentaje_uso, 4),
        "casi_agotado": secuencial.casi_agotado,
        "bloqueado": secuencial.bloqueado,
    }


def _agregar_alerta(lista: list, codigo: str, severidad: str, mensaje: str):
    lista.append({"codigo": codigo, "severidad": severidad, "mensaje": mensaje})


def armar_snapshot_empresa(empresa) -> dict:
    """
    Arma el payload pesado. Función pura, sin side effects.
    Usa las properties esta_activa y disponible para consistencia.
    """
    # Suscripción: tomar la primera activa (usar property)
    suscripcion = next(
        (s for s in empresa.suscripciones.all() if s.esta_activa),
        None,
    )

    # Paquete: tomar el primero disponible (usar property)
    paquete = next(
        (p for p in empresa.paquetes.all() if p.disponible),
        None,
    )

    # Certificado: el más reciente activo
    certificado = empresa.certificados.filter(activo=True).order_by("-creado_at").first()

    # Secuencial: el primero por tipo (snapshot del tipo más bajo)
    secuencial = empresa.secuenciales.order_by("tipo_ecf").first()

    snapshot = {
        "evento": "empresa.snapshot",
        "version": 1,
        "enviado_en": timezone.now().isoformat(),
        "empresa": {
            "id": str(empresa.id),
            "rnc": empresa.rnc,
            "razon_social": empresa.razon_social,
            "nombre_comercial": empresa.nombre_comercial,
            "ambiente": empresa.ambiente,
            "estado": empresa.estado,
            "activa": empresa.activa,
        },
        "suscripcion": _serializar_suscripcion(suscripcion),
        "paquete": _serializar_paquete(paquete),
        "certificado": _serializar_certificado(certificado),
        "secuencial": _serializar_secuencial(secuencial),
        "alertas": [],
    }

    # Alertas
    hoy = timezone.now().date()

    if paquete:
        disponibles = paquete.comprobantes_restantes
        if paquete.total_comprobantes > 0:
            pct = (disponibles / paquete.total_comprobantes) * 100
            if pct <= PCT_COMPROBANTES_BAJOS:
                _agregar_alerta(snapshot["alertas"], "COMPROBANTES_BAJOS", "WARN",
                                f"Quedan {disponibles} comprobantes disponibles ({pct:.0f}%).")
        if paquete.fecha_vencimiento:
            dias_paq = (paquete.fecha_vencimiento.date() - hoy).days
            if 0 < dias_paq <= DIAS_PAQUETE_POR_VENCER:
                _agregar_alerta(snapshot["alertas"], "PAQUETE_POR_VENCER", "WARN",
                                f"El paquete vence en {dias_paq} días.")

    if suscripcion and suscripcion.fecha_renovacion:
        dias_susc = (suscripcion.fecha_renovacion - hoy).days
        if 0 < dias_susc <= DIAS_SUSCRIPCION_POR_VENCER:
            _agregar_alerta(snapshot["alertas"], "SUSCRIPCION_POR_VENCER", "WARN",
                            f"La suscripción vence en {dias_susc} días.")

    if certificado:
        dias_cert = (certificado.vigencia_hasta - hoy).days
        if 0 < dias_cert <= DIAS_CERT_VENCE_PRONTO:
            _agregar_alerta(snapshot["alertas"], "CERT_VENCE_PRONTO", "WARN",
                            f"El certificado vence en {dias_cert} días.")
        elif dias_cert < 0:
            _agregar_alerta(snapshot["alertas"], "CERT_VENCIDO", "ERROR",
                            f"El certificado venció hace {abs(dias_cert)} días.")

    return snapshot


def dispatcher_webhook_minimo(empresa, payload: dict) -> dict:
    """
    POST al POS con el snapshot firmado por HMAC-SHA256.
    Usa webhook_secret (NO api_key.token) descifrado desde ApiKey.
    Retorna dict con {status, http_status, error}.
    NO implementa retry; eso es del Hito 4.
    """
    api_key = empresa.api_keys.filter(activa=True).order_by("-creado_at").first()
    if not api_key:
        return {"status": "skipped", "razon": "sin_api_key_activa"}

    webhook_secret = api_key.obtener_webhook_secret()
    if not webhook_secret:
        return {"status": "skipped", "razon": "sin_webhook_secret"}

    url = getattr(api_key, "webhook_url", None) or os.getenv("POS_DEFAULT_WEBHOOK_URL", "")
    if not url:
        return {"status": "skipped", "razon": "sin_webhook_url"}

    body = json.dumps(payload, default=str).encode()
    signature = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": payload["evento"],
        "X-Webhook-Delivery": str(uuid.uuid4()),
        "X-Webhook-Signature": f"sha256={signature}",
        "User-Agent": "DerejFactAPI-Webhooks/1.0",
    }

    try:
        resp = requests.post(url, data=body, headers=headers, timeout=10)
    except requests.RequestException as exc:
        logger.error(f"webhook_dispatcher_error empresa={empresa.rnc} error={exc}")
        return {"status": "failed", "error": str(exc)[:500]}

    if 200 <= resp.status_code < 300:
        logger.info(f"webhook_dispatcher_ok empresa={empresa.rnc} http={resp.status_code}")
        return {"status": "delivered", "http_status": resp.status_code}
    else:
        logger.warning(f"webhook_dispatcher_non2xx empresa={empresa.rnc} http={resp.status_code}")
        return {"status": "failed", "http_status": resp.status_code, "response": resp.text[:500]}
```

### `apps/empresas/tasks.py` (nuevo)

```python
"""
apps/empresas/tasks.py

Tareas Celery para el snapshot de empresa.
- enviar_snapshot_empresa(): snapshot de una empresa
- enviar_snapshot_diario(): snapshot de todas las empresas (Celery Beat 06:00)
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def enviar_snapshot_empresa(self, empresa_id: str):
    """Envía snapshot a una empresa específica."""
    try:
        from empresas.models import Empresa
        empresa = Empresa.objects.get(pk=empresa_id, activa=True, deleted_at__isnull=True)
    except Empresa.DoesNotExist:
        logger.warning(f"snapshot_skip empresa_id={empresa_id} razon=no_existe_o_inactiva")
        return {"status": "skipped", "razon": "empresa_no_existe_o_inactiva"}

    from empresas.services import armar_snapshot_empresa, dispatcher_webhook_minimo
    payload = armar_snapshot_empresa(empresa)
    resultado = dispatcher_webhook_minimo(empresa, payload)
    logger.info(f"snapshot_result empresa={empresa.rnc} resultado={resultado}")
    return resultado


@shared_task
def enviar_snapshot_diario():
    """Recorre todas las empresas activas y dispara snapshot."""
    from empresas.models import Empresa
    empresas = Empresa.objects.filter(activa=True, deleted_at__isnull=True)
    total = empresas.count()
    for empresa in empresas.iterator():
        # Usar delay (no apply_async) para distribuir la carga en workers
        enviar_snapshot_empresa.delay(str(empresa.id))
    logger.info(f"snapshot_diario_dispatched total={total}")
    return {"total": total}
```

### `apps/empresas/signals.py` (nuevo)

```python
"""
apps/empresas/signals.py

Signals que disparan snapshot de empresa al cambiar modelos estructurales.
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="subscriptions.Suscripcion")
def snapshot_on_suscripcion(sender, instance, created, **kwargs):
    transaction.on_commit(
        lambda: __import__("empresas.tasks", fromlist=["enviar_snapshot_empresa"])
        .enviar_snapshot_empresa.delay(str(instance.empresa_id))
    )


@receiver(post_save, sender="subscriptions.PaqueteComprobantes")
def snapshot_on_paquete(sender, instance, created, **kwargs):
    transaction.on_commit(
        lambda: __import__("empresas.tasks", fromlist=["enviar_snapshot_empresa"])
        .enviar_snapshot_empresa.delay(str(instance.empresa_id))
    )


@receiver(post_save, sender="sequences.Secuencial")
def snapshot_on_secuencial(sender, instance, created, **kwargs):
    transaction.on_commit(
        lambda: __import__("empresas.tasks", fromlist=["enviar_snapshot_empresa"])
        .enviar_snapshot_empresa.delay(str(instance.empresa_id))
    )


@receiver(post_save, sender="empresas.CertificadoDigital")
def snapshot_on_certificado(sender, instance, created, **kwargs):
    transaction.on_commit(
        lambda: __import__("empresas.tasks", fromlist=["enviar_snapshot_empresa"])
        .enviar_snapshot_empresa.delay(str(instance.empresa_id))
    )
```

> **Importante:** Usar string sender `"subscriptions.PaqueteComprobantes"` (NO `apps.planes.Paquete` que no existe). Usar `__import__` lazy para evitar circular imports en tiempo de carga de la app.

### `apps/empresas/apps.py` (modificación)

```python
from django.apps import AppConfig


class EmpresasConfig(AppConfig):
    default_auto_field = "uuid"
    name = "empresas"
    verbose_name = "Empresas"

    def ready(self):
        # Importar signals para que se conecten los @receiver
        from . import signals  # noqa: F401
```

> **Importante:** El `import signals` en `ready()` ejecuta los `@receiver` decorators que registran los handlers. Si se renombró la app, ajustar el `name`.

### `CELERY_BEAT_SCHEDULE` en `core/settings/base.py`

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # ... existing schedules ...
    "enviar-snapshot-diario": {
        "task": "empresas.tasks.enviar_snapshot_diario",
        "schedule": crontab(hour=6, minute=0),  # 06:00 AM diario (UTC-4 America/Santo_Domingo)
        "options": {"queue": "default"},
    },
}
```

---

## 🧪 Tests

### `apps/empresas/tests.py` (+14 tests)

| # | Test | Esperado |
|---|------|----------|
| 1 | `test_armar_snapshot_estructura_completa` | Dict con todas las claves esperadas |
| 2 | `test_armar_snapshot_paquete_bajo_agrega_alerta` | `alertas` contiene `COMPROBANTES_BAJOS` cuando `disponibles <= 10%` |
| 3 | `test_armar_snapshot_cert_vence_pronto_agrega_alerta` | `alertas` contiene `CERT_VENCE_PRONTO` cuando faltan ≤ 30 días |
| 4 | `test_armar_snapshot_paquete_vencido_agrega_alerta` | `alertas` contiene `PAQUETE_POR_VENCER` cuando faltan ≤ 7 días |
| 5 | `test_armar_snapshot_suscripcion_por_vencer` | `alertas` contiene `SUSCRIPCION_POR_VENCER` cuando faltan ≤ 7 días |
| 6 | `test_armar_snapshot_suscripcion_no_activa_saltea_alertas_paquete` | Sin suscripción activa → `suscripcion: null`, sigue armando paquete/certificado |
| 7 | `test_dispatcher_webhook_firma_hmac_correcta` | Firma calculada con `webhook_secret` (NO `api_key.token`) coincide con HMAC-SHA256 del body |
| 8 | `test_dispatcher_webhook_200_es_delivered` | Retorna `status=delivered` cuando POS responde 200 |
| 9 | `test_dispatcher_webhook_500_es_failed` | Retorna `status=failed` cuando POS responde 500 |
| 10 | `test_dispatcher_webhook_sin_api_key_es_skipped` | Retorna `status=skipped` cuando no hay API-Key activa |
| 11 | `test_dispatcher_webhook_sin_webhook_secret_es_skipped` | API-Key antigua sin `webhook_secret_cifrado` → `razon=sin_webhook_secret` |
| 12 | `test_signal_suscripcion_cambio_dispara_snapshot` | Mock `enviar_snapshot_empresa.delay` es llamado tras `Suscripcion.save()` |
| 13 | `test_signal_paquete_cambio_dispara_snapshot` | Igual para `PaqueteComprobantes.save()` |
| 14 | `test_signal_secuencial_cambio_dispara_snapshot` | Igual para `Secuencial.save()` |
| 15 | `test_signal_certificado_cambio_dispara_snapshot` | Igual para `CertificadoDigital.save()` |
| 16 | `test_task_snapshot_diario_recorre_todas_las_empresas` | Mock `delay` es llamado N veces según `Empresa.objects.filter(activa=True).count()` |
| 17 | `test_task_snapshot_empresa_inexistente_es_skipped` | Retorna `razon=empresa_no_existe_o_inactiva` |
| 18 | `test_api_key_crear_genera_webhook_secret` | `ApiKey.crear()` retorna tupla de 3 valores; `webhook_secret_cifrado` está poblado |
| 19 | `test_api_key_obtener_webhook_secret_descifra` | `api_key.obtener_webhook_secret()` retorna el secret en claro |
| 20 | `test_api_key_sin_webhook_secret_retorna_none` | API-Key antigua → `obtener_webhook_secret()` retorna `None` |

**Total: ~20 tests nuevos** (los 14 originales + 6 de api_key).

### Setup necesario en tests

```python
# apps/empresas/tests.py (extender)
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from empresas.models import Empresa, CertificadoDigital
from empresas.crypto import cifrar
from sequences.models import Secuencial
from subscriptions.models import Suscripcion, PaqueteComprobantes, Plan
from api_keys.models import ApiKey
from empresas.services import armar_snapshot_empresa, dispatcher_webhook_minimo
from empresas.tasks import enviar_snapshot_empresa, enviar_snapshot_diario


class EmpresaSnapshotTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(
            rnc="131793916", razon_social="Test SRL", ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA, activa=True,
        )
        cls.plan = Plan.objects.create(
            nombre="Plan Test", limite_comprobantes=1000,
            precio_mensual=100, precio_anual=1000,
            ciclo_disponible=Plan.CICLO_AMBOS, dias_gracia=0,
        )
        cls.suscripcion = Suscripcion.objects.create(
            empresa=cls.empresa, plan=cls.plan, ciclo=Suscripcion.CICLO_MENSUAL,
            estado=Suscripcion.ESTADO_ACTIVA,
            fecha_inicio=date(2026, 1, 1),
            fecha_renovacion=date(2026, 7, 1),
        )
        cls.paquete = PaqueteComprobantes.objects.create(
            empresa=cls.empresa, suscripcion=cls.suscripcion, plan=cls.plan,
            total_comprobantes=1000, comprobantes_usados=150,
            estado=PaqueteComprobantes.ESTADO_ACTIVO,
            fecha_vencimiento=timezone.now() + timedelta(days=30),
        )
        cls.cert = CertificadoDigital.objects.create(
            empresa=cls.empresa, alias="Test",
            archivo=SimpleUploadedFile("test.p12", b"fake", content_type="application/x-pkcs12"),
            pin_cifrado=cifrar("1234"),
            vigencia_desde=date(2026, 1, 15),
            vigencia_hasta=date(2027, 1, 15),
            activo=True,
        )
        cls.secuencial = Secuencial.objects.create(
            empresa=cls.empresa, tipo_ecf=31, ultimo_numero=150,
        )
        cls.api_key, cls.token, cls.webhook_secret = ApiKey.crear(
            empresa=cls.empresa, nombre="POS Test", creado_por=None,
            scopes=["comprobantes:crear", "pos:ready"],
        )
```

### Tests de `apps/api_keys/tests.py` (extender)

```python
def test_create_returns_webhook_secret_only_once(self):
    payload = {
        "empresa": str(self.empresa.id),
        "nombre": "POS Test",
        "scopes": ["comprobantes:crear", "pos:ready"],
    }
    create_resp = self.client.post(self.base_url, payload, format="json")
    self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
    self.assertIn("token", create_resp.data)
    self.assertIn("webhook_secret", create_resp.data)
    key_id = create_resp.data["id"]

    # GET no expone ninguno de los dos
    detail_resp = self.client.get(f"{self.base_url}{key_id}/")
    self.assertNotIn("token", detail_resp.data)
    self.assertNotIn("webhook_secret", detail_resp.data)
```

---

## 🔧 Comandos para correr tests

```bash
# Solo empresas
python manage.py test apps.empresas -v 2

# Solo api_keys (para el secret)
python manage.py test apps.api_keys -v 2

# Con Celery eager (para tests de tasks)
CELERY_TASK_ALWAYS_EAGER=True python manage.py test apps.empresas -v 2
```

---

## ⚠️ Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| `ApiKey.crear()` retorna 3 valores; rompe call sites existentes | Buscar todos los `ApiKey.crear(` con grep y actualizar |
| Signals disparan en bulk operations (ej. seed de datos) | Usar `transaction.on_commit` para evitar envíos en transacciones abortadas |
| 06:00 AM es hora punta del servidor | `enviar_snapshot_diario` solo dispara `delay`; los workers procesan en paralelo |
| Empresa sin `webhook_url` en API-Key | Fallback a `POS_DEFAULT_WEBHOOK_URL` del `.env`; si tampoco existe, `skipped` |
| Cambios en `Comprobante` NO disparan snapshot | Correcto: el snapshot es estructural, no transaccional. Comprobantes usan su propio evento (`comprobante.aceptado`) |
| Tests de Celery requieren `CELERY_TASK_ALWAYS_EAGER=True` | Configurar en `settings/test.py` o variable de entorno |
| Falla de un snapshot no debe abortar el batch | `enviar_snapshot_diario` solo dispara; cada `delay` es independiente |
| `armar_snapshot_empresa` con empresa sin paquete | Retorna `paquete: null` + `alertas: []`; el POS interpreta como "sin paquete, no emitir" |
| API-Key antigua sin `webhook_secret` | Dispatcher retorna `skipped:sin_webhook_secret` (no rompe el snapshot, solo no lo entrega) |
| HMAC verification rota con API-Key rotada | Al rotar, el nuevo `webhook_secret` se devuelve una vez. El POS debe actualizar su copia local |
| `apps.empresas.signals` causa import circular | Usar `__import__("empresas.tasks", ...)` lazy dentro del lambda |

---

## 📅 Plan de ejecución (orden de implementación)

1. **Modificar `apps/api_keys/models.py`**: agregar `webhook_secret_cifrado` y `obtener_webhook_secret()`. Actualizar `ApiKey.crear()` para retornar 3 valores. **Actualizar todos los call sites** (`apps/api_keys/tests.py`, `apps/pos/tests.py`, scripts). Commit.
2. **Generar migration** para el nuevo campo: `python manage.py makemigrations api_keys`. Commit.
3. **Modificar `apps/api_keys/serializers.py` y `views.py`**: exponer `webhook_secret` en `create()` solo. Commit.
4. **Crear `apps/empresas/services.py`** con `armar_snapshot_empresa()` y helpers. Tests unitarios (4-6 tests). Commit.
5. **Modificar `apps/empresas/apps.py`**: agregar `ready()` que importa `signals`. Commit.
6. **Crear `apps/empresas/signals.py`**: 4 signals. Tests con mock de `delay`. Commit.
7. **Crear `apps/empresas/tasks.py`**: `enviar_snapshot_empresa()` y `enviar_snapshot_diario()`. Tests. Commit.
8. **Agregar `dispatcher_webhook_minimo()`** en `services.py` con HMAC-SHA256 usando `webhook_secret`. Tests de firma + casos de respuesta. Commit.
9. **Configurar `CELERY_BEAT_SCHEDULE`** en `core/settings/base.py`. Commit.
10. **Actualizar `docs/integracion.md`**: nueva sección 13 con evento `empresa.snapshot`, gestión de secretos, headers, formato de firma. Commit.
11. **Actualizar `docs/plan_fase2.md`**: insertar Hito 0.6 con link a este documento. Commit.
12. **Correr suite completa**: `python manage.py test apps.empresas apps.api_keys -v 2`. Verificar 20/20.
13. **Probar manualmente**: `python manage.py shell` → `from empresas.tasks import enviar_snapshot_empresa; enviar_snapshot_empresa("<empresa_id>")` con servidor POS local (puerto 8001) que loguee la firma esperada.
14. **Push y verificar deploy** (cuando el usuario lo apruebe).

---

## ✅ Criterios de aceptación

1. **`ApiKey.crear()`:**
   - Retorna tupla de 3 valores: `(instancia, token, webhook_secret)`.
   - `webhook_secret_cifrado` se guarda en DB (cifrado Fernet).
   - `obtener_webhook_secret()` descifra y retorna el secret en claro.
   - API-Keys antiguas (sin `webhook_secret_cifrado`) siguen funcionando para auth, pero no firman webhooks.

2. **`armar_snapshot_empresa(empresa)`:**
   - Retorna dict con la estructura completa: `evento`, `version`, `enviado_en`, `empresa`, `suscripcion`, `paquete`, `secuencial`, `certificado`, `alertas`.
   - Usa `suscripcion.esta_activa` (no filter manual por estado).
   - Usa `paquete.disponible` (no filter manual por estado + fecha).
   - Usa `paquete.comprobantes_restantes` (no cálculo inline).
   - `alertas` se llena con `COMPROBANTES_BAJOS` cuando `disponibles <= 10%`.
   - `alertas` se llena con `CERT_VENCE_PRONTO` cuando faltan ≤ 30 días.
   - `alertas` se llena con `PAQUETE_POR_VENCER` cuando faltan ≤ 7 días.
   - `alertas` se llena con `SUSCRIPCION_POR_VENCER` cuando faltan ≤ 7 días.
   - Si no hay suscripción activa, `suscripcion: null` y el resto del payload sigue armado.

3. **`dispatcher_webhook_minimo(empresa, payload)`:**
   - Firma `X-Webhook-Signature: sha256=<hex>` calculada con HMAC-SHA256 del body usando `webhook_secret` descifrado (NO `api_key.token`).
   - Retorna `status=delivered` cuando el POS responde 2xx.
   - Retorna `status=failed` cuando responde ≥ 400 o hay error de red.
   - Retorna `status=skipped` cuando la empresa no tiene API-Key activa.
   - Retorna `status=skipped` con `razon=sin_webhook_secret` para API-Keys antiguas.

4. **Tasks Celery:**
   - `enviar_snapshot_empresa(empresa_id)` se puede llamar manualmente y procesa una empresa.
   - `enviar_snapshot_diario()` dispara N tasks (uno por empresa activa) y retorna `{"total": N, ...}`.
   - En `CELERY_BEAT_SCHEDULE` aparece con cron `0 6 * * *` (06:00 AM diario).

5. **Signals:**
   - `post_save` en `Suscripcion` dispara `enviar_snapshot_empresa.delay()`.
   - `post_save` en `PaqueteComprobantes` dispara `enviar_snapshot_empresa.delay()`.
   - `post_save` en `Secuencial` dispara `enviar_snapshot_empresa.delay()`.
   - `post_save` en `CertificadoDigital` dispara `enviar_snapshot_empresa.delay()`.
   - Todos usan `transaction.on_commit` para evitar envíos en transacciones fallidas.

6. **Documentación:**
   - `docs/integracion.md` nueva sección 13 con: nombre del evento, payload, headers, formato de firma, gestión de `webhook_secret`, triggers.
   - `docs/plan_fase2.md` con Hito 0.6 marcado y link a este documento.

7. **Tests:**
   - ~20 tests nuevos pasan.
   - Cero regresiones en tests existentes.
   - `apps/api_keys/tests.py` actualizado: `test_create_returns_webhook_secret_only_once` pasa.

8. **No se toca:**
   - Lógica de firma de XMLs (sigue server-side en Hito 3).
   - Validator `pos/ready/` (vive en `plan_secuenciales_refactor.md`).
   - CRUD de webhooks (Hito 4).
   - Eventos transaccionales de comprobantes (`comprobante.aceptado`, etc.).

---

## 🔗 Referencias cruzadas

- [`plan_fase2.md`](./plan_fase2.md) — Plan maestro Fase 2 (Hito 0.6 referenciado aquí)
- [`plan_secuenciales_refactor.md`](./plan_secuenciales_refactor.md) — POS-Ready validator ligero
- `docs/integracion.md` — Documentación de integración con el POS
- `apps/empresas/models.py` — Modelos `Empresa`, `CertificadoDigital`
- `apps/empresas/crypto.py` — `cifrar()`, `descifrar()` (Fernet)
- `apps/sequences/models.py` — Modelo `Secuencial` y properties (`porcentaje_uso`, `casi_agotado`, `proximo_encf`)
- `apps/subscriptions/models.py` — `Suscripcion.esta_activa`, `PaqueteComprobantes.disponible`, `PaqueteComprobantes.comprobantes_restantes`
- `apps/api_keys/models.py` — `ApiKey` con nuevo campo `webhook_secret_cifrado`
- `core/settings/base.py` — Configuración de Celery + `CELERY_BEAT_SCHEDULE`

---

## 🚦 Estado

- [x] Plan completo y aprobado
- [ ] `apps/api_keys/models.py` con `webhook_secret_cifrado` + `obtener_webhook_secret()` (breaking change en `crear()`)
- [ ] Migration `0004_*` para `webhook_secret_cifrado`
- [ ] `apps/api_keys/serializers.py` y `views.py` exponen `webhook_secret` solo en create
- [ ] Tests de `api_keys` actualizados (incluye `test_create_returns_webhook_secret_only_once`)
- [ ] `apps/empresas/services.py` (armar_snapshot_empresa, dispatcher_webhook_minimo)
- [ ] Tests de `armar_snapshot_empresa` (6 tests)
- [ ] Tests de `dispatcher_webhook_minimo` (5 tests)
- [ ] `apps/empresas/tasks.py` (enviar_snapshot_empresa, enviar_snapshot_diario)
- [ ] `apps/empresas/signals.py` (4 signals)
- [ ] `apps/empresas/apps.py` (ready importa signals)
- [ ] `CELERY_BEAT_SCHEDULE` en `base.py`
- [ ] Tests de tasks y signals (6 tests)
- [ ] `docs/integracion.md` actualizado (nueva sección 13)
- [ ] `docs/plan_fase2.md` actualizado (Hito 0.6)
- [ ] Suite completa pasa (20/20)
- [ ] Push a repo + deploy verificado
