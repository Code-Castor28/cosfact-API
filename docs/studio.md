# Estudio técnico — DerejFactAPI

> **Documento de referencia para colaboradores nuevos.**
> Fecha del estudio: 19 de noviembre de 2026.
> Base analizada: rama `main`, commit `623af6d` (7 de junio de 2026).
> Alcance: código real, migraciones, configuración y documentación existente.
> El árbol de trabajo presenta cambios de fin de línea (CRLF/LF) sin cambios funcionales.

---

## Tabla de contenidos

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Stack tecnológico](#2-stack-tecnológico)
3. [Arquitectura y apps](#3-arquitectura-y-apps)
4. [Modelo de datos](#4-modelo-de-datos)
5. [Autenticación y scopes](#5-autenticación-y-scopes)
6. [Inventario de endpoints](#6-inventario-de-endpoints)
7. [Máquinas de estado](#7-máquinas-de-estado)
8. [App DGII en profundidad](#8-app-dgii-en-profundidad)
9. [Tareas asíncronas (Celery)](#9-tareas-asíncronas-celery)
10. [Pagos y suscripciones](#10-pagos-y-suscripciones)
11. [Webhooks y notificaciones](#11-webhooks-y-notificaciones)
12. [Pruebas y CI](#12-pruebas-y-ci)
13. [Hallazgos críticos consolidados](#13-hallazgos-críticos-consolidados)
14. [Estado de la documentación](#14-estado-de-la-documentación)
15. [Entorno local y comandos](#15-entorno-local-y-comandos)
16. [Glosario](#16-glosario)

---

## 1. Resumen ejecutivo

DerejFactAPI es un **middleware SaaS de facturación electrónica (e-CF)** para la República Dominicana. Se sitúa entre los sistemas POS de los comercios y la DGII: valida la venta, reserva un e-NCF, construye y firma el XML, lo transmite y notifica el veredicto fiscal.

### Qué está sólido

- Aislamiento multi-tenant por `empresa` (RNC) en todas las apps transaccionales.
- Modelo de datos completo, con FKs `PROTECT`, UUID y triggers de inmutabilidad.
- Separación conceptual entre ciclo interno (`estado`) y veredicto fiscal (`estado_dgii`).
- Firma XML PKCS#12 funcional a nivel criptográfico.
- Bitácora `DGIILog` cifrada y append-only.
- Webhooks con HMAC, reintentos y backoff con jitter.
- Catálogos DGII editables y seed por comando.
- ~146 funciones de prueba.

### Qué falta o está roto

- El pipeline fiscal **no está cerrado**: la autenticación de la DGII (`ValidarSemilla`) no está implementada.
- El XML no cumple el XSD oficial y usa campos legacy vacíos.
- El veredicto fiscal no se refleja en `estado`; la inmutabilidad nunca se activa.
- Los reintentos chocan con la propia máquina de estados.
- El onboarding (`POST /api/v1/secuencias/`) está implementado pero **no montado** en el URLconf.
- Varias tareas de notificación referencian campos inexistentes.
- La documentación histórica describe un sistema más avanzado que el código.

### Progreso declarado (contradictorio)

| Fuente | Total declarado |
|---|---|
| `README.md` | 31/31 |
| `AGENTS.md` | 41/44 |
| `docs/estado.md` y `docs/ejecucion.md` | 48/49 |

La cifra más reciente es **48/49**. La única tarea abierta declarada es la 4.3 (documentación de PDF), aunque los endpoints PDF ya existen. En cambio, la 4.2 (`POST /api/v1/tasks/run/`) está marcada como hecha y **no existe en código**.

---

## 2. Stack tecnológico

| Componente | Versión / tecnología |
|---|---|
| Framework | Django 5.0.6 + Django REST Framework 3.17.1 |
| Base de datos | PostgreSQL |
| Cola de tareas | Celery 5.6.3 + Redis |
| Beat | `django-celery-beat` |
| Criptografía | `cryptography` (Fernet, PKCS#12) |
| XML | `lxml` + `xmlsec` 1.3.15 |
| Autenticación humana | JWT (`djangorestframework-simplejwt`) |
| Autenticación POS | API Key propia con scopes |
| PDF | `reportlab` 4.2.0 |
| Monitoreo | Sentry SDK 2.60.0 |
| Servidor | Gunicorn + Nginx |

> Hay migraciones generadas con Django 6.0.5 aunque el proyecto declara 5.0.6. Conviene regenerarlas o documentar la versión real usada.

---

## 3. Arquitectura y apps

```
[POS — API Key]
      │
      ▼
┌──────────────────────────────────────────────────┐
│ Nginx + Gunicorn (Django + DRF)                  │
│                                                   │
│ api_keys        → valida token, IP y scopes       │
│ subscriptions   → saldo de comprobantes           │
│ sequences       → e-NCF atómico + onboarding      │
│ comprobantes    → motor de venta y estados        │
│ dgii            → XML, firma, SOAP, bitácora      │
│ webhooks        → notificación al POS             │
│ notificaciones  → correos a humanos               │
│ audit           → bitácora append-only            │
└───────┬────────────────────────────────┬──────────┘
        │                                │
        ▼                                ▼
   PostgreSQL                       Redis (broker)
                                         │
                                         ▼
                                  Celery Worker / Beat
                                         │
                                         ▼
                                  DGII (SOAP/HTTPS)
```

| App | Responsabilidad | Modelos clave |
|---|---|---|
| `users` | Usuarios del panel, roles y sesiones | `Usuario` |
| `empresas` | Identidad fiscal, certificado y tokens DGII | `Empresa`, `CertificadoDigital`, `TokenDGII` |
| `api_keys` | Tokens del POS con scopes, IP y rate limit | `ApiKey` |
| `subscriptions` | Planes, contratos y saldo de comprobantes | `Plan`, `Suscripcion`, `PaqueteComprobantes` |
| `sequences` | Rangos e-NCF y numeración atómica | `Secuencial`, `NumeroViciado`, `MovimientoSecuencial` |
| `clientes` | Directorio fiscal opcional del comprador | `Cliente` |
| `comprobantes` | Venta diaria, validación matemática y estados | `Comprobante`, `ComprobanteDetalle`, `ComprobanteEvento` |
| `dgii` | Firma, envío, consulta, logs y catálogos | `DGIILog`, `Provincia`, `Municipio`, etc. |
| `webhooks` | Entrega asíncrona de eventos al POS | `Webhook`, `WebhookEntrega` |
| `notificaciones` | Correos HTML y su bitácora | `LogNotificacion` |
| `audit` | Auditoría inmutable de acciones críticas | `AuditLog` |
| `pagos` | Caja del SaaS y recibos PDF | `Pago`, `HistorialPago` |

### Regla de aislamiento

Toda consulta transaccional filtra por `empresa`. Las vistas resuelven la empresa según el tipo de autenticación:

```python
# API Key → request.user es Empresa
# JWT      → request.user es Usuario, con .empresa
empresa = request.user if isinstance(request.user, Empresa) else request.user.empresa
```

---

## 4. Modelo de datos

### Identidad y acceso

| Modelo | Campos relevantes | Notas |
|---|---|---|
| `Usuario` | `email` único, `rol`, `empresa`, bloqueo por intentos | Roles: `SUPERADMIN`, `ADMIN_EMPRESA`, `USUARIO_EMPRESA` |
| `Empresa` | `rnc` único, `ambiente`, `estado`, `activa`, `onboarding_bloqueado` | Ambientes: `testecf`, `certecf`, `ecf`. Soft delete |
| `CertificadoDigital` | `archivo` `.p12`, `pin_cifrado`, `vigencia_hasta`, `activo` | PIN cifrado con Fernet |
| `TokenDGII` | `ambiente`, `token_cifrado`, `expira_at`, `activo` | Único activo por empresa/ambiente |
| `ApiKey` | `prefix`, `key_hash` SHA-256, `scopes`, `allowed_ips` | El token completo se muestra una sola vez |

### Comercial

| Modelo | Campos relevantes |
|---|---|
| `Plan` | `limite_comprobantes`, precios, `ciclo_disponible`, `dias_gracia` |
| `Suscripcion` | `empresa`, `plan`, `ciclo`, `estado`, `fecha_renovacion` |
| `PaqueteComprobantes` | `total_comprobantes`, `comprobantes_usados`, `estado`, `origen` |
| `Pago` | `monto`, `tipo_pago`, `metodo_pago`, `referencia`, `estado` |
| `HistorialPago` | `pago` (1:1), `paquete`, período, monto |

### Fiscal

| Modelo | Campos relevantes |
|---|---|
| `Secuencial` | `empresa`, `tipo_ecf`, `ultimo_numero`, `minimo_asignado`, `maximo_asignado`, `bloqueado` |
| `NumeroViciado` | `empresa`, `encf`, `motivo` (⚠️ no se escribe en producción) |
| `MovimientoSecuencial` | Trazabilidad de cada e-NCF asignado |
| `Comprobante` | `encf`, montos, `estado`, `estado_dgii`, `track_id_dgii`, `xml_path`, `idempotency_key` |
| `ComprobanteDetalle` | Líneas DGII + campos legacy |
| `ComprobanteEvento` | Historial append-only de cambios de estado |

### Operación

| Modelo | Campos relevantes |
|---|---|
| `DGIILog` | Tipo de operación, endpoint, HTTP status, XML cifrado, estado de respuesta |
| `Webhook` / `WebhookEntrega` | URL, eventos, secret hash, intentos, estado |
| `AuditLog` | Actor, acción, recurso, IP, payload hash, firma HMAC |
| `LogNotificacion` | Destinatario, tipo, estado, error |

---

## 5. Autenticación y scopes

### JWT

- `POST /api/v1/auth/login/` con `email` y `password`.
- Access token: 1 día. Refresh: 7 días.
- Header: `Authorization: Bearer <token>`.

### API Key (POS)

- Header: `Authorization: Api-Key <rnc_sin_guiones>_<token>`.
- Solo se guarda el SHA-256; el token se muestra una vez al crearlo.
- Se valida: empresa activa, IP permitida (si `allowed_ips` no está vacío) y scope.

### Scopes reales

| Scope | Endpoint previsto |
|---|---|
| `comprobantes:crear` | `POST /api/v1/comprobantes/` |
| `comprobantes:consultar` | `GET /api/v1/comprobantes/...` |
| `comprobantes:anular` | Anulación (sin endpoint implementado) |
| `secuenciales:consultar` | `GET /api/v1/secuenciales/...` |
| `empresa:onboarding` | `POST /api/v1/secuencias/` |

> La documentación antigua usa `comprobantes:emision`, que **no existe** en el código.

### Problemas de implementación

1. **Los scopes GET no se aplican.** `SCOPE_PATTERNS` usa `"GET  /api/v1/..."` (dos espacios) pero la ruta se compone con uno (`apps/api_keys/authentication.py:7-12,48`). Ningún GET valida scope.
2. **Las acciones POST de comprobantes no tienen scope.** Solo el `POST /api/v1/comprobantes/` exacto está mapeado; `emitir/`, `reintentar/` y `consultar-dgii/` no exigen scope.
3. **`ComprobanteViewSet` solo acepta API-Key** (`authentication_classes = [ApiKeyAuthentication]`). El JWT del panel no puede leer comprobantes por API.
4. **`recover-password` bloquea cuentas**: cambia la contraseña a una aleatoria y no la entrega (solo la loguea en DEBUG).

---

## 6. Inventario de endpoints

> DRF añade `HEAD`, `OPTIONS` y variantes `.json`. No se listan.

### Autenticación y salud

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| `POST` | `/api/v1/auth/login/` | Público | Access + refresh JWT |
| `POST` | `/api/v1/auth/token/refresh/` | Público | Renueva access |
| `POST` | `/api/v1/auth/recover-password/` | Público | ⚠️ Recuperación simulada |
| `GET` | `/api/v1/health/` | Público | Estado del servicio y DB |

**Ejemplo de login:**

```bash
curl -X POST https://tu-dominio/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@ejemplo.com", "password": "Test123456"}'
```

```json
{
  "access": "<jwt_access>",
  "refresh": "<jwt_refresh>"
}
```

### Usuarios

| Método | Ruta | Acceso |
|---|---|---|
| `GET/POST` | `/api/v1/usuarios/` | JWT |
| `GET/PUT/PATCH/DELETE` | `/api/v1/usuarios/{id}/` | JWT |
| `GET/PUT/PATCH` | `/api/v1/usuarios/me/` | JWT |
| `POST` | `/api/v1/usuarios/me/change-password/` | JWT |

### Empresas

| Método | Ruta | Acceso |
|---|---|---|
| `GET/POST` | `/api/v1/empresas/` | JWT; API-Key solo lectura de la propia |
| `GET/PUT/PATCH/DELETE` | `/api/v1/empresas/{id}/` | JWT (escritura SuperAdmin) |
| `GET` | `/api/v1/empresas/{id}/suscripcion/` | JWT |
| `GET` | `/api/v1/empresas/{id}/comprobantes/` | JWT |

### Planes, suscripciones y paquetes

| Método | Ruta | Acceso |
|---|---|---|
| `GET/POST` + CRUD | `/api/v1/planes/`, `/api/v1/planes/{id}/` | JWT |
| `GET/POST` + CRUD | `/api/v1/suscripciones/`, `/api/v1/suscripciones/{id}/` | JWT |
| `GET/POST` + CRUD | `/api/v1/paquetes/`, `/api/v1/paquetes/{id}/` | JWT |

### API Keys

| Método | Ruta | Acceso |
|---|---|---|
| `GET/POST` + CRUD | `/api/v1/api-keys/`, `/api/v1/api-keys/{id}/` | JWT SuperAdmin |
| `POST` | `/api/v1/api-keys/{id}/revocar/` | JWT SuperAdmin |
| `POST` | `/api/v1/api-keys/{id}/rotar/` | JWT SuperAdmin |

**Ejemplo de creación:**

```bash
curl -X POST https://tu-dominio/api/v1/api-keys/ \
  -H "Authorization: Bearer <jwt_superadmin>" \
  -H "Content-Type: application/json" \
  -d '{
    "empresa": "UUID_DE_LA_EMPRESA",
    "nombre": "POS Principal",
    "scopes": ["comprobantes:crear", "comprobantes:consultar", "secuenciales:consultar"],
    "allowed_ips": [],
    "expira_at": "2027-01-01T00:00:00Z"
  }'
```

La respuesta incluye `token` **una sola vez**.

### Secuencias

| Método | Ruta | Acceso |
|---|---|---|
| `GET/POST` + CRUD | `/api/v1/secuenciales/`, `/api/v1/secuenciales/{id}/` | JWT |
| `GET` | `/api/v1/secuenciales/{id}/preview/` | JWT |
| `POST` | `/api/v1/secuenciales/{id}/bloquear/` | JWT |
| `POST` | `/api/v1/secuenciales/{id}/desbloquear/` | JWT |
| `POST` | `/api/v1/secuencias/` | ⚠️ **No montado** |

> `onboarding()` existe en `apps/sequences/views.py`, pero `sequences.urls` no se incluye en `core/urls.py`. La ruta es inalcanzable por HTTP.

### Comprobantes — solo API-Key

| Método | Ruta | Scope |
|---|---|---|
| `GET/POST` | `/api/v1/comprobantes/` | `comprobantes:consultar` / `comprobantes:crear` |
| `GET/PUT/PATCH/DELETE` | `/api/v1/comprobantes/{id}/` | `comprobantes:consultar` (GET) |
| `POST` | `/api/v1/comprobantes/{id}/consultar-dgii/` | ⚠️ sin scope |
| `POST` | `/api/v1/comprobantes/{id}/reintentar/` | ⚠️ sin scope |
| `POST` | `/api/v1/comprobantes/{id}/emitir/` | ⚠️ sin scope |

**Ejemplo de creación de comprobante:**

```bash
curl -X POST https://tu-dominio/api/v1/comprobantes/ \
  -H "Authorization: Api-Key 131793916_xxxxxxxx" \
  -H "Idempotency-Key: 6f1c2b9e-3a4d-4c7e-9b2a-1f0e5d6c7b8a" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_ecf": 32,
    "monto_total": "118.00",
    "monto_gravado": "100.00",
    "monto_itbis": "18.00",
    "monto_exento": "0.00",
    "monto_impuesto_adicional": "0.00",
    "detalles": [{
      "numero_linea": 1,
      "indicador_facturacion": 1,
      "nombre_item": "Producto demo",
      "cantidad": "1.00",
      "unidad_medida": 1,
      "precio_unitario_item": "100.00",
      "descuento_monto": "0.00",
      "monto_item": "100.00"
    }]
  }'
```

Respuesta:

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "e_ncf": "E320000000001",
  "server_timestamp": "2026-11-19T14:00:00Z",
  "codigo_seguridad": "",
  "valor_pagar": "118.00",
  "sequence_status": "consumed"
}
```

> `codigo_seguridad` sale vacío porque la firma no extrae el `SignatureValue`.

### Clientes

| Método | Ruta | Acceso |
|---|---|---|
| `GET/POST` + CRUD | `/api/v1/clientes/`, `/api/v1/clientes/{rnc_cedula}/` | JWT / API-Key |

### DGII — catálogos y logs

| Método | Ruta | Acceso |
|---|---|---|
| CRUD | `/api/v1/provincias/`, `/municipios/`, `/unidades-medida/`, `/monedas/`, `/impuestos-adicionales/`, `/formas-pago/` | Lectura autenticada; escritura SuperAdmin |
| `GET` | `/api/v1/dgii/logs/`, `/api/v1/dgii/logs/{id}/` | JWT, read-only |

### Webhooks — solo API-Key

| Método | Ruta | Acceso |
|---|---|---|
| `GET/POST` + CRUD | `/api/v1/webhooks/`, `/api/v1/webhooks/{id}/` | API-Key |
| `GET` | `/api/v1/webhooks/{id}/entregas/` | API-Key |

### Pagos — SuperAdmin

| Método | Ruta | Acceso |
|---|---|---|
| `GET/POST` + CRUD | `/api/v1/pagos/`, `/api/v1/pagos/{id}/` | JWT SuperAdmin |
| `PATCH` | `/api/v1/pagos/{id}/actualizar_confirmacion/` | JWT SuperAdmin |
| `POST` | `/api/v1/pagos/{id}/rechazar/` | JWT SuperAdmin |
| `GET` | `/api/v1/pagos/historial/` | JWT SuperAdmin |
| `GET` | `/api/v1/pagos/{id}/pdf/a4/` | JWT SuperAdmin |
| `GET` | `/api/v1/pagos/{id}/pdf/80mm/` | JWT SuperAdmin |

### Admin y debug

| Ruta | Notas |
|---|---|
| `/admin/` | Panel Django |
| `/admin/api-keys/crear/` | Formulario custom que muestra el token |
| `/api/v1/` | API root de DRF |
| `/sentry-debug/` | Solo `DEBUG` |
| `/static/`, `/media/` | Solo `DEBUG` |

### Endpoints documentados que no existen

| Ruta | Situación |
|---|---|
| `POST /api/v1/tasks/run/` | No existe `apps/tasks/` ni vista ni ruta |
| `POST /api/v1/pagos/{id}/confirmar/` | Nunca existió; la confirmación real es `PATCH .../actualizar_confirmacion/` |
| `/api/v1/pos/ready/` | No existe |
| `POST /api/v1/secuencias/` | Existe la vista, pero no está montada |

---

## 7. Máquinas de estado

### `Comprobante.estado` — ciclo interno

| Estado | Significado |
|---|---|
| `BORRADOR` | Validado, aún no emitido |
| `PENDIENTE` | Listo para emitir |
| `PROCESANDO` | Definido, pero **inalcanzable** en el código actual |
| `EMITIDO` | Enviado a DGII (o intento iniciado) |
| `ACEPTADO` | Aceptado fiscalmente |
| `RECHAZADO` | Rechazado por DGII |
| `ANULADO` | Anulado |
| `ERROR` | Error técnico (sin llamadas en producción) |
| `CONTINGENCIA` | DGII no disponible |

Transiciones reales (`apps/comprobantes/models.py:261-271`):

```text
BORRADOR     → PENDIENTE, EMITIDO
PENDIENTE    → PROCESANDO, EMITIDO
PROCESANDO   → ACEPTADO, RECHAZADO, ERROR, CONTINGENCIA
EMITIDO      → ANULADO, CONTINGENCIA
ACEPTADO     → ANULADO
RECHAZADO    → BORRADOR
ERROR        → PENDIENTE
CONTINGENCIA → PENDIENTE
ANULADO      → (terminal)
```

### `Comprobante.estado_dgii` — comunicación fiscal

| Estado | Significado |
|---|---|
| `SIN_ENVIAR` | Nunca se envió |
| `ENVIADO` | Enviado, sin veredicto |
| `ACEPTADO` | DGII aceptó |
| `RECHAZADO` | DGII rechazó |
| `CONTINGENCIA` | Timeout o caída |
| `REINTENTANDO` | Reintento en curso |
| `ERROR_RED` | Error de red/HTTP |

Transiciones reales (`apps/comprobantes/models.py:273-281`):

```text
SIN_ENVIAR   → ENVIADO
ENVIADO      → ACEPTADO, RECHAZADO, CONTINGENCIA, ERROR_RED
RECHAZADO    → REINTENTANDO
CONTINGENCIA → REINTENTANDO
ERROR_RED    → REINTENTANDO
REINTENTANDO → ENVIADO
ACEPTADO     → (terminal)
```

### El problema de sincronización

`emitir_ecf` pone `estado=EMITIDO` y `estado_dgii=ENVIADO`. Después, `consultar_estado` solo actualiza `estado_dgii`. Por tanto:

- `estado` **nunca** llega a `ACEPTADO` ni `RECHAZADO`.
- `ESTADOS_INMUTABLES = {ACEPTADO, ANULADO}` nunca se activa.
- El trigger de inmutabilidad de PostgreSQL tampoco se activa.
- Un comprobante aceptado sigue siendo editable.

---

## 8. App DGII en profundidad

### 8.1 Responsabilidad y archivos

La app `dgii` es la **pasarela fiscal**: construye el XML, lo firma, lo envía, consulta el veredicto y deja bitácora. No gestiona la venta; eso corresponde a `comprobantes`.

| Archivo | Rol |
|---|---|
| `apps/dgii/models.py` | `DGIILog` append-only y re-export de catálogos |
| `apps/dgii/services.py` | Orquestador: `emitir_ecf`, `consultar_estado`, contingencias |
| `apps/dgii/tasks.py` | Reintento asíncrono y barrido nocturno |
| `apps/dgii/utils/dgii_client.py` | Cliente HTTP: token, semilla, envío, consulta, logs |
| `apps/dgii/utils/xml_builder.py` | Construcción del XML e-CF |
| `apps/dgii/utils/xml_signer.py` | Firma XML con xmlsec + PKCS#12 |
| `apps/dgii/serializers.py` | Serializers de catálogos y `DGIILog` |
| `apps/dgii/views.py` | ViewSets de catálogos y logs |
| `apps/dgii/urls.py` | Rutas de catálogos y `/dgii/logs/` |
| `apps/dgii/admin.py` | Admin de catálogos + log inmutable |
| `apps/dgii/catalogs/models.py` | 6 tablas de referencia DGII |
| `management/commands/cargar_catalogos_dgii.py` | Seed de catálogos |

### 8.2 Piezas de datos

```text
Empresa (RNC, ambiente testecf/certecf/ecf)
   ├── CertificadoDigital (.p12 + pin_cifrado con Fernet)
   ├── TokenDGII (token cifrado, expira_at)
   └── Comprobantes
         ├── Comprobante (estado, estado_dgii, encf, track_id_dgii)
         ├── ComprobanteDetalle (líneas)
         ├── ComprobanteEvento (historial append-only)
         └── DGIILog (bitácora de cada llamada)
```

- **`CertificadoDigital`**: identidad criptográfica. Debe existir, tener `.p12`, PIN cifrado y `activo=True`.
- **`TokenDGII`**: cachea el token de autenticación por empresa/ambiente.
- **`Comprobante.estado` / `estado_dgii`**: dos máquinas separadas.
- **`DGIILog`**: cada operación; el XML se cifra con Fernet antes de persistir.

### 8.3 Flujo completo de emisión

```text
POS/API                          API (Django)                         DGII
  │ POST /comprobantes/     ──►  create_comprobante
  │                               BORRADOR → PENDIENTE, e-NCF, cuota
  │
  │ POST /{id}/emitir/      ──►  emitir_ecf
  │                               ├─ estado=EMITIDO, estado_dgii=ENVIADO
  │                               ├─ build_ecf_xml
  │                               ├─ CertificadoDigital (.p12) + PIN Fernet
  │                               ├─ sign_xml (xmlsec)
  │                               ├─ guarda XML en disco + SHA-256
  │                               └─ DgiiClient.enviar_ecf
  │                                       ├─ TokenDGII cacheado
  │                                       └─ _autenticar (ValidarSemilla) ❌
  │                                       └─ POST /Recepcion/...  ──────►  DGII
  │                               ◄─ track_id, estado=None
  │                               estado_dgii = ENVIADO (nunca ACEPTADO)
  │
  │ POST /{id}/consultar-dgii/ ─►  consultar_estado
  │                               ├─ GET /Consultas/.../{track_id} ───►  DGII
  │                               ◄─ Estado (parse regex)
  │                               ├─ estado_dgii = valor crudo
  │                               └─ webhook si ACEPTADO/RECHAZADO
  │
  │ Beat 02:00               ──►  reintentar_contingencia
  │                               └─ reintentar_envio_ecf → emitir_ecf
  │                                       ❌ transición inválida
```

### 8.4 Emisión paso a paso

Se dispara por `POST /api/v1/comprobantes/{id}/emitir/` o por la tarea de reintento. Llama a `emitir_ecf()` (`apps/dgii/services.py:117`).

**Paso 1 — Bloqueo y validaciones**

```python
with transaction.atomic():
    comprobante = Comprobante.objects.select_for_update().select_related("empresa").get(pk=...)
    if estado_dgii == ACEPTADO:
        return comprobante
    if estado_dgii == RECHAZADO and not forzar_reintento:
        return comprobante
```

Si falta el e-NCF, se solicita a `sequences.obtener_proximo_encf()`.

**Paso 2 — Marca de salida**

```python
comprobante.estado = "EMITIDO"
comprobante.estado_dgii = "ENVIADO"
comprobante.save(update_fields=["encf", "estado", "estado_dgii", "actualizado_at"])
_crear_evento(comprobante, estado_anterior, comprobante.estado, "Inicio de envio DGII")
```

**Paso 3 — `_ejecutar_envio()`** (`services.py:90-114`)

1. `build_ecf_xml(comprobante, detalles)`.
2. `_cert_path_for_empresa()` → ruta del `.p12`.
3. `_get_cert_pin()` → descifra el PIN con Fernet.
4. `sign_xml()` → XML firmado.
5. `_save_xml()` → escribe en disco y calcula SHA-256:
   ```text
   {XML_BASE_PATH o /var/derejfact/xmls/}/{empresa_id}/ecf/{año}/{encf}.xml
   ```
6. Actualiza `xml_path`, `xml_hash`, `xml_version="1.0"`.
7. `DgiiClient(empresa).enviar_ecf(xml_firmado)`.

**Paso 4 — Cliente DGII**

1. `_get_token()`: busca un `TokenDGII` activo que no expire en el próximo minuto.
2. Si no hay, `_autenticar()` pide la semilla y **lanza `"ValidarSemilla no implementado"`** (`dgii_client.py:101`).
3. Con token: `POST /Recepcion/api/FacturasElectronicas` con `Authorization: Bearer` y el XML.
4. Extrae `<TrackId>` por regex y devuelve `{"track_id": ..., "estado": None}`.

**Paso 5 — Respuesta**

- `estado == "ACEPTADO"` → `estado_dgii = ACEPTADO`.
- `estado == "RECHAZADO"` → `estado_dgii = RECHAZADO`.
- Como el cliente **siempre devuelve `None`**, el comprobante queda en `ENVIADO`.

Después: guarda `track_id`, incrementa `intentos_envio`, crea `DGIILog(ENVIO_ECF)` y dispara webhook solo si el estado es ACEPTADO/RECHAZADO (nunca en este punto).

**Paso 6 — Errores**

| Caso | Acción |
|---|---|
| Mensaje contiene “timeout”/“timed out” | `_marcar_contingencia`: `estado=CONTINGENCIA`, `estado_dgii=CONTINGENCIA`, `intentos+1` |
| Otro error de red/HTTP | `_marcar_error_red`: solo `estado_dgii=ERROR_RED`, `estado` sigue `EMITIDO` |
| Error técnico | `marcar_error_tecnico()` existe, pero no tiene llamadas |

Luego re-lanza la excepción: la vista responde `503` o la tarea Celery reintenta.

### 8.5 Construcción del XML

`build_ecf_xml()` (`xml_builder.py:7-41`) genera una estructura mínima:

```xml
<ECF xmlns="http://dgii.gov.do/ecf" Id="ECF">
  <Version>1.0</Version>
  <Encabezado>
    <IdDoc>
      <TipoeCF>32</TipoeCF>
      <eNCF>E320000000001</eNCF>
      <FechaEmision>2026-11-19T14:00:00</FechaEmision>
    </IdDoc>
    <Emisor>
      <RNCEmisor>131793916</RNCEmisor>
    </Emisor>
    <Comprador>
      <RNCComprador>00123456789</RNCComprador>
      <RazonSocialComprador>Cliente Demo</RazonSocialComprador>
    </Comprador>
    <Totales>
      <MontoGravadoTotal>100.00</MontoGravadoTotal>
      <MontoExento>0.00</MontoExento>
      <TotalITBIS18>18.00</TotalITBIS18>
      <MontoTotal>118.00</MontoTotal>
    </Totales>
  </Encabezado>
  <DetalleItems>
    <Item>
      <NumeroLinea>1</NumeroLinea>
      <NombreItem>Producto demo</NombreItem>
      <CantidadItem>1.00</CantidadItem>
      <PrecioUnitarioItem>100.00</PrecioUnitarioItem>
      <SubtotalItem>100.00</SubtotalItem>
    </Item>
  </DetalleItems>
</ECF>
```

**Problema 1 — campos legacy.** El builder lee `detalle.descripcion`, `detalle.precio_unitario` y `detalle.subtotal` (`xml_builder.py:36-39`), pero el serializer y el service llenan `nombre_item`, `precio_unitario_item` y `monto_item` (`comprobantes/models.py:449-454`). Los legacy quedan vacíos o en cero: **el XML sale con nombre vacío y precios en cero**.

**Problema 2 — XSD incompleto.** Faltan nodos obligatorios: `RazonSocialEmisor`, `DireccionEmisor`, `TipoPago`, `FormaPago`, `TotalITBIS1/2/3`, `MontoImpuestoAdicional`, `IndicadorFacturacion`, `UnidadMedida`, `MontoItem`, `DescuentoMonto`, etc. La estructura actual no pasa validación formal.

### 8.6 Firma XML

`sign_xml()` (`xml_signer.py:8-36`):

1. Parsea el XML y registra `Id` con `xmlsec.tree.add_ids(root, ["Id"])`.
2. Crea `<ds:Signature>` con `EXCL_C14N` + `RSA_SHA256`.
3. Referencia `SHA256` con `URI="#ECF"` y transform `ENVELOPED`.
4. Agrega `KeyInfo` + `X509Data`.
5. Carga el `.p12` con `xmlsec.Key.from_file(..., PKCS12_PEM/PKCS12, pin)`.
6. Firma.

Lo que **no** hace:

- No valida el XML contra el XSD antes de firmar.
- No verifica la vigencia del certificado (`vigencia_hasta`).
- No extrae los 6 primeros caracteres del `SignatureValue`.
- Por eso `codigo_seguridad_dgii` queda siempre vacío y la respuesta al POS devuelve `""`.

### 8.7 Cliente HTTP y autenticación

`DgiiClient` (`dgii_client.py`):

| Aspecto | Implementación |
|---|---|
| URL base | `https://ecf.dgii.gov.do/{ambiente}` (`:26-27`) |
| Timeout | `settings.DGII_TIMEOUT`, default 20 s |
| Token | `TokenDGII` cifrado; reutiliza si expira en >1 min |
| Autenticación | ❌ Solo pide la semilla; `ValidarSemilla` no implementado |
| Envío | `POST /Recepcion/api/FacturasElectronicas` |
| Consulta | `GET /Consultas/api/Consultas/Estado/{track_id}` |
| Parseo | Regex sobre `<TrackId>` y `<Estado>` (asume XML) |
| Logs | `_log()` cifra request/response; **silencia toda excepción** |

**Discrepancia de ambientes:** la documentación habla de hosts `testecf.dgii.gov.do`, `certecf.dgii.gov.do` y `ecf.dgii.gov.do`. El código arma `ecf.dgii.gov.do/{testecf|certecf|ecf}`, que no coincide.

**Consecuencia:** sin un `TokenDGII` válido, ningún envío llega a DGII. El workaround actual es insertar manualmente un token con `token_cifrado` y `expira_at` futuro.

### 8.8 Consulta del veredicto

`POST /api/v1/comprobantes/{id}/consultar-dgii/` → `consultar_estado()` (`services.py:266`).

1. Si no hay `track_id_dgii`, no hace nada.
2. `GET /Consultas/api/Consultas/Estado/{track_id}`.
3. Extrae `<Estado>` por regex.
4. Asigna **el valor crudo** a `estado_dgii`.
5. Crea `DGIILog(CONSULTA_ESTADO)`.
6. Dispara webhook si es `ACEPTADO` o `RECHAZADO`.

**Problema:** `Comprobante.save()` valida transiciones. Si DGII devuelve `PENDIENTE` o `TIMEOUT`, el valor no está en `TRANSICIONES_ESTADO_DGII` y el guardado lanza `ValidationError`. Hoy solo funcionan `ACEPTADO`, `RECHAZADO` y `CONTINGENCIA` desde `ENVIADO`.

### 8.9 Reintentos y contingencia

**Tarea `reintentar_envio_ecf`** (`tasks.py:8-19`):

- `max_retries=5`.
- Guarda `celery_task_id` en el comprobante.
- Llama `emitir_ecf(..., forzar_reintento=True)`.
- Si falla, reintenta con `backoff_con_jitter` de `webhooks.services`.

**Tarea `reintentar_contingencia`** (`tasks.py:22-28`):

- Beat la ejecuta a las **02:00** (`core/celery.py:29-36`).
- Busca `Comprobante.objects.filter(estado="CONTINGENCIA")` y encola cada uno.

**Problema de fondo:** `emitir_ecf` fuerza `estado → EMITIDO` y `estado_dgii → ENVIADO`, pero la tabla de transiciones no permite:

- `CONTINGENCIA → EMITIDO` ni `CONTINGENCIA → ENVIADO`.
- `ERROR_RED → ENVIADO` (solo `ERROR_RED → REINTENTANDO`).
- `RECHAZADO → EMITIDO/ENVIADO` (solo `RECHAZADO → REINTENTANDO`).

El reintento manual y el nocturno **fallan en la máquina de estados**; como la tarea captura toda excepción, reintenta 5 veces un error de lógica como si fuera de red.

Backoff real: `[60, 300, 900, 3600, 14400]` segundos, con jitter de 0–10 %.

### 8.10 Bitácora `DGIILog`

- Campos: empresa, comprobante, ambiente, tipo de operación, endpoint, HTTP status, XML cifrado, estado de respuesta, código DGII, mensaje, `exitoso`, duración, `respuesta_raw`, `celery_task_id`.
- **Append-only** en modelo (`save()`/`delete()` lanzan `ValidationError`) y con trigger PostgreSQL que bloquea UPDATE/DELETE.
- Consulta: `GET /api/v1/dgii/logs/` con filtros `empresa_id`, `comprobante_id`, `estado`, `tipo_operacion`, `fecha_desde`, `fecha_hasta`; paginación 50/200.
- Admin completamente read-only.

**Detalles mejorables:**

- Cada envío genera **dos logs**: uno del cliente (`_log`, sin `comprobante`) y otro de `_crear_dgiilog_envio` (con `comprobante`).
- En el log de envío, `estado_respuesta` queda vacío y `exitoso=False` porque el cliente devuelve `estado=None`.
- `codigo_dgii` guarda el `track_id`, no un código de error.
- `_log` se traga excepciones (`except Exception: pass`): si falla el cifrado o la escritura, se pierde trazabilidad sin aviso.

### 8.11 Catálogos DGII

6 modelos con el código DGII como PK: `Provincia`, `Municipio`, `UnidadMedida`, `Moneda`, `ImpuestoAdicional`, `FormaPago`.

- Seed: `python manage.py cargar_catalogos_dgii`.
- Endpoints: `/api/v1/provincias/`, `/municipios/`, `/unidades-medida/`, `/monedas/`, `/impuestos-adicionales/`, `/formas-pago/`.
- Lectura autenticada; escritura solo SuperAdmin.
- Admin editable para cambios de códigos o tasas.

**Ojo con el seed:** solo las primeras 6 provincias tienen municipios; de la 07 a la 32 la lista está vacía (`cargar_catalogos_dgii.py:150-175`). El catálogo queda incompleto.

### 8.12 Endpoints DGII y ejemplos

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/api/v1/comprobantes/{id}/emitir/` | API-Key | Emisión síncrona |
| `POST` | `/api/v1/comprobantes/{id}/consultar-dgii/` | API-Key | Consulta veredicto |
| `POST` | `/api/v1/comprobantes/{id}/reintentar/` | API-Key | Encola reintento (202) |
| `GET` | `/api/v1/dgii/logs/` | JWT | Bitácora con filtros |
| `GET` | `/api/v1/dgii/logs/{id}/` | JWT | Detalle de log |
| CRUD | Catálogos (`/provincias/`, etc.) | JWT | Referencia DGII |

**Emitir:**

```bash
curl -X POST https://tu-dominio/api/v1/comprobantes/550e8400-e29b-41d4-a716-446655440000/emitir/ \
  -H "Authorization: Api-Key 131793916_xxxxxxxx"
```

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "encf": "E320000000001",
  "estado": "EMITIDO",
  "estado_dgii": "ENVIADO"
}
```

**Consultar:**

```bash
curl -X POST https://tu-dominio/api/v1/comprobantes/550e8400-e29b-41d4-a716-446655440000/consultar-dgii/ \
  -H "Authorization: Api-Key 131793916_xxxxxxxx"
```

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "estado_dgii": "ACEPTADO"
}
```

**Reintentar:**

```bash
curl -X POST https://tu-dominio/api/v1/comprobantes/550e8400-e29b-41d4-a716-446655440000/reintentar/ \
  -H "Authorization: Api-Key 131793916_xxxxxxxx"
```

```json
{
  "detail": "Reintento encolado.",
  "task_id": "a1b2c3d4-..."
}
```

**Logs:**

```bash
curl "https://tu-dominio/api/v1/dgii/logs/?tipo_operacion=ENVIO_ECF&estado=ACEPTADO" \
  -H "Authorization: Bearer <jwt>"
```

**Catálogo:**

```bash
curl https://tu-dominio/api/v1/provincias/ -H "Authorization: Bearer <jwt>"
```

### 8.13 Qué funciona y qué no

#### ✅ Implementado

- Modelo de datos completo y separación `estado` / `estado_dgii`.
- Construcción y firma XML funcional a nivel criptográfico (los tests de firma pasan).
- Cliente HTTP con timeout, token cacheado y parseo de TrackId/Estado.
- Bitácora cifrada, append-only, con API y admin.
- Reintentos con backoff + jitter y barrido nocturno.
- Catálogos y seed.

#### ❌ Pendiente o roto

| # | Problema | Archivo |
|:--|---|---|
| 1 | `ValidarSemilla` no implementado → no hay autenticación | `dgii_client.py:85-101` |
| 2 | URL base no coincide con los hosts DGII por ambiente | `dgii_client.py:26-27` |
| 3 | XML usa campos legacy vacíos → ítems sin nombre/precio | `xml_builder.py:36-39` |
| 4 | XML incompleto frente al XSD oficial | `xml_builder.py:7-41` |
| 5 | `enviar_ecf` devuelve `estado=None` → nunca ACEPTADO/RECHAZADO | `dgii_client.py:121-124` |
| 6 | `estado` se queda en `EMITIDO` → inmutabilidad nunca se activa | `services.py:146`, `models.py:78` |
| 7 | Reintentos incompatibles con `TRANSICIONES_PERMITIDAS` | `services.py:146`, `models.py:261-281` |
| 8 | `codigo_seguridad_dgii` nunca se calcula | `xml_signer.py:8-36` |
| 9 | `consultar_estado` asigna valores crudos y puede romper `save()` | `services.py:274-282` |
| 10 | Certificado vencido no se detecta antes de firmar | `services.py:28-49` |
| 11 | `_log` silencia errores y duplica registros | `dgii_client.py:29-53` |
| 12 | `ERROR_RED` no lo reintenta el Beat (solo `CONTINGENCIA`) | `tasks.py:26` |
| 13 | `NumeroViciado` no se escribe en producción | `sequences/models.py:162` |
| 14 | Seed de municipios incompleto (provincias 07–32) | `cargar_catalogos_dgii.py:150-175` |

### 8.14 Cómo probar el pipeline sin DGII real

1. `python manage.py cargar_catalogos_dgii`
2. Crear `Empresa` con `ambiente="testecf"`.
3. Crear `CertificadoDigital` con `.p12` y `pin_cifrado = empresas.crypto.cifrar("PIN")`.
4. Insertar un `TokenDGII` con `token_cifrado`, `expira_at` futuro y `activo=True` (evita `_autenticar`).
5. Crear plan, suscripción, paquete y secuencial.
6. Crear API Key con scope `comprobantes:crear`.
7. `POST /api/v1/comprobantes/` y luego `POST /{id}/emitir/`.
8. Revisar `GET /api/v1/dgii/logs/` y el XML en `/var/derejfact/xmls/...`.

Aun así, contra la DGII real fallará por autenticación y XML. Sirve para validar el pipeline interno.

---

## 9. Tareas asíncronas (Celery)

### Tareas registradas (9)

| Tarea | Disparador |
|---|---|
| `webhooks.services.entregar_webhook` | `disparar_webhook` |
| `dgii.tasks.reintentar_envio_ecf` | `reintentar_contingencia` y action `reintentar` |
| `dgii.reintentar_contingencia` | Beat 02:00 |
| `pagos.generar_pagos_automaticos` | Beat 00:00 |
| `pagos.notificar_pagos_proximos` | Beat 08:00 |
| `notificaciones.enviar_recibo_pago` | Confirmación de pago |
| `notificaciones.alertar_balance_bajo` | Beat 06:00 |
| `notificaciones.alertar_certificado_vencimiento` | Beat 06:30 |
| `notificaciones.alertar_suscripcion_vencimiento` | `pagos.notificar_pagos_proximos` |

### Beat

```text
00:00  pagos.generar_pagos_automaticos
02:00  dgii.reintentar_contingencia
06:00  notificaciones.alertar_balance_bajo
06:30  notificaciones.alertar_certificado_vencimiento
08:00  pagos.notificar_pagos_proximos
```

En desarrollo, `CELERY_TASK_ALWAYS_EAGER=True`: los `.delay()` se ejecutan en proceso.

---

## 10. Pagos y suscripciones

### Flujo de confirmación

`PATCH /api/v1/pagos/{id}/actualizar_confirmacion/`:

1. Valida que el pago esté `PENDIENTE`.
2. Exige referencia si el método no es `EFECTIVO`.
3. Dentro de `transaction.atomic()`:
   - Marca el pago `CONFIRMADO`.
   - Si es `RENOVACION`: avanza `fecha_inicio`/`fecha_renovacion`, crea `PaqueteComprobantes` e `HistorialPago`.
   - Si es `ADICIONAL`: crea un paquete extra sin tocar fechas.
4. Fuera de la transacción: `enviar_recibo_pago.delay(pago.id)`.

### Prorrateo del primer pago

- Mensual: `precio_mensual × días_usados / días_del_período`.
- Anual: `precio_anual × días_usados / 365` (366 en bisiesto).

### Problemas

- Si ya existe historial del período, el código **confirma el pago** (`pago.save()`) y luego retorna `400` dentro del `atomic()`: la transacción hace commit del estado `CONFIRMADO` sin crear paquete.
- `Empresa.onboarding_bloqueado` solo se pone en `True` (`comprobantes/services.py:47`); **nunca se vuelve a `False`** al confirmar un pago.
- `HistorialPago` perdió su `unique_together` y no tiene constraint sustituto.
- `Pago.fecha_corte` es `null=True` en el modelo, pero la columna DB sigue `NOT NULL`.

---

## 11. Webhooks y notificaciones

### Webhooks

- Eventos disponibles: `comprobante.aceptado`, `comprobante.rechazado`, `comprobante.anulado`, `paquete.agotado`, `certificado.por_vencer`.
- Entrega: `POST` con headers `X-DerejSoft-Signature` y `X-DerejSoft-Event`.
- Máximo 5 intentos con backoff.

**Problemas:**

- `Webhook.MAX_INTENTOS` no existe (es constante de módulo) → `AttributeError` al primer fallo.
- La firma HMAC usa `secret_hash`, no el secret original: el receptor no puede verificarla.
- `eventos__contains` sobre `JSONField` depende de PostgreSQL y no tiene índice GIN.

### Notificaciones

Tareas: recibo de pago, balance bajo, certificado por vencer, suscripción por vencer.

**Problemas:** usan campos inexistentes:

- `paquete.cantidad_inicial` / `paquete.cantidad_consumida` → son `total_comprobantes` / `comprobantes_usados`.
- `CertificadoDigital.fecha_vencimiento` → es `vigencia_hasta`.
- `empresa.nombre` → es `razon_social` / `nombre_comercial`.

---

## 12. Pruebas y CI

### Inventario aproximado (~146 funciones)

| Archivo | # | Cobertura |
|---|---:|---|
| `apps/comprobantes/tests.py` | 25 | Máquina de estados `estado_dgii` |
| `apps/sequences/tests.py` | 27 | e-NCF, `NumeroViciado`, SaaS Guard |
| `apps/subscriptions/tests.py` | 19 | Planes, paquetes, consumo |
| `apps/pagos/tests/test_tasks.py` | 19 | Generación automática y notificaciones |
| `apps/webhooks/tests.py` | 16 | HMAC, backoff, reintentos |
| `tests/dgii/test_xml_signing.py` | 15 | Firma, `codigo_seguridad`, certificado |
| `apps/clientes/tests.py` | 13 | CRUD y validación RNC |
| `apps/empresas/tests.py` | 5 | Certificado y Fernet |
| `apps/api_keys/tests.py` | 4 | Token, scopes, rotación |
| `apps/users/tests.py` | 3 | Restricciones de API-Key |
| `apps/audit/tests.py` | 0 | Placeholder |
| `apps/dgii/tests.py` | 0 | Placeholder |

### Brechas

- No hay `pytest.ini` ni `pytest-django`; la suite Django se ejecuta con `manage.py test`.
- Falta `tests/fixtures/test_pin.txt`, referenciado por `tests/dgii/conftest.py`.
- El CI solo despliega; no ejecuta tests ni lint.
- Los tests de firma con DB requieren PostgreSQL.

---

## 13. Hallazgos críticos consolidados

| Severidad | Hallazgo | Impacto |
|---|---|---|
| 🔴 | `ValidarSemilla` no implementado | Ningún envío real a DGII |
| 🔴 | Onboarding no montado | No se pueden cargar rangos ni certificado vía API |
| 🔴 | XML usa campos legacy vacíos | Ítems sin nombre/precio ante DGII |
| 🔴 | XML incompleto vs XSD | Rechazo formal de DGII |
| 🔴 | Reintentos vs máquina de estados | Contingencia y ERROR_RED quedan atrapados |
| 🔴 | `estado` nunca pasa a ACEPTADO | Inmutabilidad y auditoría fiscal no se activan |
| 🔴 | Scopes GET no se aplican | Cualquier API Key lee comprobantes/secuenciales |
| 🔴 | Acciones POST sin scope | Cualquier API Key puede emitir/reintentar |
| 🔴 | `recover-password` rota la contraseña sin entregarla | Bloqueo de cuentas |
| 🔴 | Trigger de auditoría bloquea el `UPDATE` de la firma | `AuditLog` falla en PostgreSQL |
| 🟠 | Tareas de notificación con campos inexistentes | Alertas y recibos fallan |
| 🟠 | `Webhook.MAX_INTENTOS` inexistente | Entrega falla al primer reintento |
| 🟠 | HMAC con `secret_hash` | El POS no puede verificar la firma |
| 🟠 | `codigo_seguridad_dgii` vacío | Ticket sin código de seguridad |
| 🟠 | Pago confirmado con `400` posterior | Pago sin paquete |
| 🟠 | `onboarding_bloqueado` nunca se resetea | Empresa bloqueada permanentemente |
| 🟠 | `partial_update` usa serializer de detalle | Edición de borradores rota |
| 🟠 | `DGIILog` duplicado y silencioso | Trazabilidad incompleta |

---

## 14. Estado de la documentación

| Documento | Afirmación | Realidad |
|---|---|---|
| `README.md` | 31/31 | Desactualizado; faltan Fase 4, DGII y tests XML |
| `AGENTS.md` | 41/44 | No coincide con `estado.md` (48/49) |
| `docs/arqui.md` | `EN_COLA`, `FALLO_CONEXION`, `ERROR_CERTIFICADO`, `comprobantes:emision`, XML en PostgreSQL | No existen en código |
| `docs/arqui.md` | `/api/v1/pos/ready/` | No existe |
| `docs/integracion.md` | `comprobantes/` pendiente | Ya está implementado |
| `docs/contexto.md` | Rutas `/sequences/`, `/users/login/`, scopes `emitir/consultar/anular` | No coinciden con el código |
| `docs/ejecucion.md` | `POST /api/v1/tasks/run/` ✅ | No existe |
| `docs/CELERY_SETUP.md` | Tareas con prefijo `apps.` | Los nombres reales no llevan `apps.` |
| `docs/SENTRY_SETUP.md` | `sentry_sdk.init` en `base.py` | Está en `core/wsgi.py` |

> `docs/SENTRY_SETUP.md` contiene un DSN real en texto plano. Conviene rotarlo y redactarlo.

---

## 15. Entorno local y comandos

### Instalación

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Base de datos

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py cargar_catalogos_dgii
```

### Servidor

```bash
python manage.py runserver
```

### Celery

```bash
celery -A core worker -l info
celery -A core beat -l info
```

### Tests

```bash
python manage.py test
pytest tests/dgii/test_xml_signing.py
```

### Certificado de prueba

```bash
python scripts/generate_test_cert.py
```

### Variables de entorno requeridas (nombres)

`SECRET_KEY`, `DEBUG`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `FERNET_KEY`, `DGII_CERT_PATH`, `DGII_CERT_PASSWORD`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SENTRY_DSN`, `EMAIL_*`.

> `DJANGO_SETTINGS_MODULE` se fija con `setdefault` en `manage.py` y `core/celery.py` antes de leer el `.env`; un valor en `.env` no lo sobrescribe.

---

## 16. Glosario

| Término | Significado |
|---|---|
| **e-CF** | Comprobante Fiscal Electrónico |
| **e-NCF** | Número de Comprobante Fiscal Electrónico (13 caracteres: `E` + tipo 2 + secuencial 10) |
| **RNC** | Registro Nacional del Contribuyente |
| **ITBIS** | Impuesto sobre Transferencia de Bienes Industrializados y Servicios |
| **DGII** | Dirección General de Impuestos Internos |
| **TrackId** | Identificador de seguimiento que devuelve DGII al recibir un e-CF |
| **Semilla** | Valor que DGII entrega para iniciar la autenticación |
| **PKCS#12 / .p12** | Contenedor del certificado y clave privada usado para firmar |
| **Fernet** | Cifrado simétrico autenticado usado para PIN y tokens |
| **XSD** | Esquema XML que define la estructura válida del e-CF |
| **XMLDSig** | Estándar de firma digital XML |
| **SaaS Guard** | Validación de que el volumen de rangos no exceda el plan |

---

## Anexo A — Matriz rápida de permisos

| Módulo | JWT | API-Key | SuperAdmin |
|---|---|---|---|
| Usuarios | ✅ | ❌ | Crear/eliminar |
| Empresas | ✅ | Solo lectura propia | CRUD |
| API Keys | ✅ | ❌ | CRUD |
| Planes/Suscripciones/Paquetes | ✅ | Lectura según empresa | CRUD |
| Secuenciales | ✅ | GET (scope roto) | CRUD |
| Comprobantes | ❌ | ✅ | ❌ |
| Clientes | ✅ | ✅ | — |
| DGII catálogos | ✅ | ❌ | Escritura |
| DGII logs | ✅ | ❌ | Lectura total |
| Webhooks | ❌ | ✅ | — |
| Pagos | ✅ | ❌ | ✅ |

---

## Anexo B — Checklist para un colaborador nuevo

1. Leer este documento y `docs/ejecucion.md`.
2. Confirmar el estado real con `git log` y `git status`.
3. No asumir que `docs/arqui.md` refleja el código.
4. Antes de tocar DGII, verificar `TRANSICIONES_PERMITIDAS` y `TRANSICIONES_ESTADO_DGII`.
5. Antes de documentar un endpoint, comprobar que está montado en `core/urls.py`.
6. Revisar los triggers de inmutabilidad antes de añadir `UPDATE` a modelos append-only.
7. Ejecutar `python manage.py check` y la suite antes de desplegar.
8. Actualizar `docs/ejecucion.md` y `docs/estado.md` en cada cambio, según `AGENTS.md`.

---

*Estudio elaborado a partir de lectura estática del código, migraciones y documentación. No se ejecutó la suite de pruebas ni se realizaron llamadas reales a la DGII.*
