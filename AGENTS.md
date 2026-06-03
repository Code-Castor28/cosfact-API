# Developer Notes

## Django Version

**Production y Development:** Django 5.0.6

---

## Roadmap por Fase

| Fase | Objetivo |
|:-----|:---------|
| **0 — Seguridad y Estabilidad** (✅ 6/6) | Dejar el sistema existente sin bugs que rompan acceso, expongan datos o bloqueen operaciones. Nada nuevo se construye aquí. |
| **1a — Infraestructura** (✅ 2/2) | Establecer las guardas de seguridad y el onboarding antes de construir comprobantes. Sin scopes, cualquier API Key accessa todo. Sin onboarding, no hay secuencias asignadas. |
| **1b — Comprobantes CRUD** (✅ 4/4) | Construir la app `comprobantes` completa. Al finalizar, el POS puede emitir su primer e-CF real. |
| **1c — Parches de Validación + Blindaje** (✅ 4/4) | Cerrar agujeros de validación y blindar la máquina de estados del e-CF. |
| **2 — Webhooks y Notificaciones** (✅ 9/9) | Cerrar el ciclo de vida del comprobante. El POS se entera del veredicto fiscal. El humano recibe correos relevantes. |
| **3 — Deuda Técnica** (✅ 6/6) | Pulir la calidad del código antes de abrir a más clientes. No es bloqueante para producción. |

Progreso: **✅ 31/31 — FASE 3 COMPLETA** — Docs de referencia: `docs/ejecucion.md`, `docs/estado.md`.
