# Estado de Ejecución — DerejFactAPI
> Actualizado: 2 de junio de 2026
> Referencia: `docs/ejecucion.md` v2.0.0

---

## Dashboard

| Fase | Completado | Total |
|:-----|:----------:|:-----:|
| Fase 0 — Seguridad y Estabilidad | 0 | 6 |
| Fase 1a — Infraestructura (Scopes + Onboarding) | 0 | 2 |
| Fase 1b — Comprobantes CRUD | 0 | 4 |
| Fase 1c — Parches de Validación + Blindaje | 0 | 4 |
| Fase 2 — Webhooks y Notificaciones | 0 | 9 |
| Fase 3 — Deuda Técnica | 0 | 6 |
| **Total** | **0** | **31** |

---

## ✅ Resuelto

_(nada aún — ningún hallazgo corregido)_

---

## 🔄 En Progreso

_(nada aún)_

---

## ⬜ Pendiente

### Fase 0 — Seguridad y Estabilidad
- ⬜ 0.1 Permisos de Pagos (`is_superuser` → `rol`)
- ⬜ 0.2 ClienteViewSet con JWT (`_get_empresa()`)
- ⬜ 0.3 RecoverPasswordView (eliminar `temp_password`)
- ⬜ 0.4 `ValueError` → `ValidationError` en audit/dgii
- ⬜ 0.5 Activar middleware de auditoría + fix `Api-Key`
- ⬜ 0.6 Rotar credenciales expuestas del `.env`

### Fase 1a — Infraestructura
- ⬜ 1.1 Validación de Scopes en `ApiKeyAuthentication`
- ⬜ 1.2 Endpoint Onboarding `POST /api/v1/secuencias/`

### Fase 1b — Comprobantes CRUD
- ⬜ 1.3 Serializers (motor matemático ROUND_HALF_UP)
- ⬜ 1.4 Service + ViewSet (flujo POS atómico)
- ⬜ 1.5 Conectar consumo de balance al flujo síncrono
- ⬜ 1.6 Migraciones de base de datos

### Fase 1c — Parches de Validación + Blindaje
- ⬜ 1.7 Control de e-NCF viciados (`NumeroViciado`)
- ⬜ 1.8 Corregir lógica E32 (umbral + cédula)
- ⬜ 1.10 Validación MontoTotal para E34
- ⬜ 1.11 Implementar `validate_transition()`

### Fase 2 — Webhooks y Notificaciones
- ⬜ 2.1 Webhook Serializers
- ⬜ 2.2 Webhook Views (CRUD + entregas)
- ⬜ 2.3 Webhook Services + Tasks (reintentos HMAC)
- ⬜ 2.4 Disparar webhooks desde `dgii/tasks.py`
- ⬜ 2.5 App notificaciones (models + services)
- ⬜ 2.6 Tasks de notificaciones + templates
- ⬜ 2.7 Completar `notificar_pagos_proximos`
- ⬜ 2.8 Celery Beat nocturno (`CONTINGENCIA`)
- ⬜ 2.9 Backoff con jitter en reintentos

### Fase 3 — Deuda Técnica
- ⬜ 3.1 `CleanModelSerializer` con `partial=True`
- ⬜ 3.2 HMAC con `id` y `creado_at`
- ⬜ 3.3 Idempotency Key (header del POS)
- ⬜ 3.4 Tests: sequences, subscriptions, webhooks
- ⬜ 3.5 Documentar `certecf` + `USUARIO_EMPRESA`
- ⬜ 3.6 Catálogos DGII como modelos editables vía admin

---

## Historial de Avance

| Fecha | Fase | Task | Cambio |
|:-----|:-----|:----|:-------|
| 2026-06-02 | — | — | Plan creado con 31 tasks en 6 fases |
