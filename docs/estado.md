# Estado de Ejecución — DerejFactAPI
> Actualizado: 19 de noviembre de 2026
> Referencia: `docs/ejecucion.md` v2.5.0

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
| Documentación — Estudio Técnico | 1 | 1 |
| **Total** | **49** | **50** |
| Corrección Fiscal — CF.0 (Seguridad) | 0 | 4 |
| Corrección Fiscal — CF.1 (Estados) | 0 | 4 |
| Corrección Fiscal — CF.2 (Firma/XML) | 0 | 4 |
| Corrección Fiscal — CF.3 (Operación) | 0 | 4 |
| Corrección Fiscal — CF.4 (Secundarias) | 0 | 7 |

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

### Documentación — Estudio Técnico
- ✅ DOC.1 `docs/studio.md` creado: radiografía completa del sistema real, inventario de endpoints con ejemplos, capítulo profundo de la app DGII, máquinas de estado, Celery, pruebas/CI y 18 hallazgos críticos consolidados

---

## ⚠️ Discrepancias detectadas en la auditoría (2026-11-19)

> Detectadas al redactar `docs/studio.md`. Se conservan las marcas históricas, pero **no se sostienen contra el código actual**.

| Task | Marca histórica | Realidad en código |
|:-----|:----------------|:-------------------|
| 1.2 Onboarding | ✅ Hecho | La vista `onboarding()` existe, pero `apps/sequences/urls.py` **no está incluido** en `core/urls.py` → ruta inalcanzable por HTTP |
| 4.2 `POST /api/v1/tasks/run/` | ✅ Hecho | No existe `apps/tasks/`, ni vista, ni ruta. Solo aparece en la documentación |
| 4.3 Documentación PDF | ⬜ Pendiente | Los endpoints `pdf/a4/` y `pdf/80mm/` ya existen y están documentados |
| Fase DGII (emisión) | ✅ 10/10 | Modelos/rutas/acciones existen, pero el pipeline no cierra: `ValidarSemilla` sin implementar, XML con campos legacy vacíos, reintentos incompatibles con la máquina de estados |
| `docs/arqui.md` | Estados y scopes | `EN_COLA`, `FALLO_CONEXION`, `ERROR_CERTIFICADO` y `comprobantes:emision` **no existen** en el código |

Estas discrepancias quedan documentadas en `docs/studio.md` (§13 y §14) como deuda técnica a resolver en una fase de corrección.

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
| 2026-11-19 | Documentación | DOC.1 | Creación de `docs/studio.md`: estudio técnico completo (arquitectura, endpoints con ejemplos, app DGII en profundidad, estados, Celery, tests/CI, hallazgos). Se registran 5 discrepancias entre docs y código |
