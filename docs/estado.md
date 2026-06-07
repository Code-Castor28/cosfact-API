# Estado de Ejecución — DerejFactAPI
> Actualizado: 7 de junio de 2026
> Referencia: `docs/ejecucion.md` v2.0.0

---

## Dashboard

| Fase | Completado | Total |
|:-----|:----------:|:-----:|
| Fase 0 — Seguridad y Estabilidad | 6 | 6 |
| Fase 1a — Infraestructura (Scopes + Onboarding) | 2 | 2 |
| Fase 1b — Comprobantes CRUD | 4 | 4 |
| Fase 1c — Parches de Validación + Blindaje | 4 | 4 |
| Fase 2 — Webhooks y Notificaciones | 9 | 9 |
| Fase 3 — Deuda Técnica | 6 | 6 |
| Fase 4 — Correcciones de Integración | 2 | 3 |
| Fase DGII — Monitoreo y Operaciones DGII | 10 | 10 |
| Tests de Firmado XML | 5 | 5 |
| **Total** | **48** | **49** |

---

## ✅ Resuelto

### Fase 0 — Seguridad y Estabilidad
- ✅ 0.1 Permisos de Pagos (`is_superuser` → `rol`)
- ✅ 0.2 ClienteViewSet con JWT (`_get_empresa()`)
- ✅ 0.3 RecoverPasswordView (eliminar `temp_password`)
- ✅ 0.4 `ValueError` → `ValidationError` en audit/dgii
- ✅ 0.5 Activar middleware de auditoría + fix `Api-Key`
- ✅ 0.6 Rotar credenciales expuestas del `.env`

### Fase 1a — Infraestructura
- ✅ 1.1 Validación de Scopes en `ApiKeyAuthentication`
- ✅ 1.2 Endpoint Onboarding `POST /api/v1/secuencias/`

### Fase 1b — Comprobantes CRUD
- ✅ 1.3 Serializers (motor matemático ROUND_HALF_UP)
- ✅ 1.4 Service + ViewSet (flujo POS atómico)
- ✅ 1.5 Conectar consumo de balance al flujo síncrono
- ✅ 1.6 Migraciones de base de datos

### Fase 1c — Parches de Validación + Blindaje
- ✅ 1.7 Control de e-NCF viciados (`NumeroViciado`)
- ✅ 1.8 Corregir lógica E32 (umbral + cédula)
- ✅ 1.10 Validación MontoTotal para E34
- ✅ 1.11 Implementar `validate_transition()`

### Fase 2 — Webhooks y Notificaciones
- ✅ 2.1 Webhook Serializers
- ✅ 2.2 Webhook Views (CRUD + entregas)
- ✅ 2.3 Webhook Services + Tasks (reintentos HMAC)
- ✅ 2.4 Disparar webhooks desde dgii/services.py
- ✅ 2.5 App notificaciones (models + services)
- ✅ 2.6 Tasks de notificaciones + templates
- ✅ 2.7 Completar `notificar_pagos_proximos`
- ✅ 2.8 Celery Beat nocturno (`CONTINGENCIA`)
- ✅ 2.9 Backoff con jitter en reintentos

---

## 🔄 En Progreso

### Fase 4 — Correcciones de Integración
- [x] 4.1 Disparar `enviar_recibo_pago` desde `_confirmar_pago_internamente`
- [x] 4.2 Endpoint `POST /api/v1/tasks/run/` para ejecutar tareas Celery manualmente
- [ ] 4.3 Endpoints PDF (`pdf/a4/` y `pdf/80mm/`) — documentación de endpoints existentes

### Fase DGII — Monitoreo y Operaciones DGII
- [x] DGII.1 Agregar campos a `DGIILog`
- [x] DGII.2 Agregar campos a `Comprobante` + `EMITIDO`
- [x] DGII.3 Actualizar `DgiiClient._log()`
- [x] DGII.4 Refactor `emitir_ecf()` y `consultar_estado()`
- [x] DGII.5 Actualizar `reintentar_envio_ecf` en tasks
- [x] DGII.6 Crear `DGIILogSerializer`
- [x] DGII.7 Actualizar `ComprobanteCreateSerializer`
- [x] DGII.8 Crear `DGIILogViewSet`
- [x] DGII.9 Agregar 3 `@action` a `ComprobanteViewSet`
- [x] DGII.10 Registrar rutas + admin

### Fase 3 — Deuda Técnica
- ✅ 3.1 `CleanModelSerializer` con `partial=True`
- ✅ 3.2 HMAC con `id` y `creado_at`
- ✅ 3.3 Idempotency Key (header del POS)
- ✅ 3.4 Tests: sequences, subscriptions, webhooks
- ✅ 3.5 Documentar `certecf` + `USUARIO_EMPRESA`
- ✅ 3.6 Catálogos DGII como modelos editables vía admin

### Tests de Firmado XML
- ✅ TXML.1 Script generación .p12 autofirmado + PIN cifrado
- ✅ TXML.2 Fixtures pytest (conftest.py): certificado, empresa, PIN Fernet
- ✅ TXML.3 Casos de prueba: carga, firma, código seguridad, certificado usado, XML mal formado, PIN incorrecto
- ✅ TXML.4 Fix `xmlsec.KeyFormat.PKCS12` → `PKCS12_PEM` (compatibilidad xmlsec 1.3.15 ↔ 1.3.17)

---

## Historial de Avance

| Fecha | Fase | Task | Cambio |
|:-----|:-----|:----|:-------|
| 2026-06-02 | — | — | Plan creado con 31 tasks en 6 fases |
| 2026-06-02 | Fase 0 | 0.1–0.6 | Fase 0 completada: 6 bugs de seguridad corregidos |
| 2026-06-02 | Fase 1a | 1.1–1.2 | Scopes con regex en ApiKeyAuthentication + endpoint onboarding POST /api/v1/secuencias/ |
| 2026-06-02 | Fase 1b | 1.3–1.6 | Serializers con ROUND_HALF_UP, service POS atómico, consumo balance, migraciones DB |
| 2026-06-02 | Fase 1c | 1.7–1.11 | NumeroViciado, fix E32 cédula, MontoTotal E34, validate_transition máquina estados |
| 2026-06-02 | Fase 2 | 2.1–2.9 | Webhooks CRUD + HMAC + servicios, disparo desde DGII, notificaciones (4 templates + tasks), backoff con jitter, Celery Beat nocturno CONTINGENCIA |
| 2026-06-02 | Fase 3 | 3.1–3.3 | CleanModelSerializer partial=True, HMAC audit con id+creado_at, Idempotency Key desde header del POS |
| 2026-06-02 | Fase 3 | 3.4–3.6 | Tests (sequences, subscriptions, webhooks), docs certecf+USUARIO_EMPRESA, Catálogos DGII (6 modelos + admin + seed command) |
| 2026-06-06 | Fase 4 | 4.1 | Plan y corrección: `enviar_recibo_pago.delay(pago.id)` desde `_confirmar_pago_internamente` |
| 2026-06-06 | Fase 4 | 4.2 | Plan: endpoint `POST /api/v1/tasks/run/` para disparar tareas Celery manualmente |
| 2026-06-06 | Fase 4 | 4.3 | Documentación de endpoints PDF `pdf/a4/` y `pdf/80mm/` en `docs/ejecucion.md` |
| 2026-06-07 | Fase DGII | — | Fase DGII creada con 10 tareas: monitoreo, consulta, reintento y emisión directa contra DGII. Separación `estado`/`estado_dgii` |
| 2026-06-07 | Fase DGII | 1–10 | Implementación completa: modelos + migraciones + cliente DGII + servicios + tasks + serializers + views + rutas + admin |
| 2026-06-07 | Fase 0.7 | Fixes | Arreglo de 7 fallos + 1 error en tests de secuencias e-NCF: `maximo_asignado` → `PositiveBigIntegerField`, `services.py` persiste `bloqueado=True` al agotar rango, tests actualizados a formato 13-char DGII |
| 2026-06-07 | Tests XML | TXML.1–4 | Tests de firmado XML con .p12 autofirmado: fixtures pytest, 10 tests pasan (2 DB-dependientes), fix `xmlsec.KeyFormat.PKCS12` → `PKCS12_PEM` (compatibilidad 1.3.15 ↔ 1.3.17) |
| 2026-06-07 | Tests XML | TXML.5 | Alineación de `build_ecf_xml()` al XSD oficial DGII: `Id="ECF"`, namespace `http://dgii.gov.do/ecf`, nombres de nodos corregidos, `sign_xml()` con `add_ids()` + `URI="#ECF"`, 13/13 tests no-DB pasan. |
