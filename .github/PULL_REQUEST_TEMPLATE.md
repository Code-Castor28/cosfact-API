## Descripción

Corrige la lógica de selección y validación del precio en `apps/pagos/tasks.py` para la generación automática de pagos.

Cambios principales:
- Obtener `monto` según `suscripcion.ciclo` (`precio_mensual` / `precio_anual`).
- Usar `suscripcion.precio_pagado` como fallback si el plan no tiene precio para el ciclo.
- Validación robusta usando `Decimal` y manejo de valores <= 0.
- Logs temporales de diagnóstico añadidos para plan/ciclo/precios.
- fix de la github accion para mejorar el flujo de despliegues
-mejor en la app de pagos
- fix de pdf
- probando la fecha ID


Incluye tests unitarios que cubren generación para ciclos `MENSUAL` y `ANUAL`.

---

### Notas para reviewers

1. Los logs de diagnóstico se agregaron intencionalmente; por favor verificar y sugerir remoción o ajuste antes del merge final.
2. Validar que el comportamiento es el esperado en staging antes de ejecutar la task en producción.

---

### Comandos para probar localmente

1. Crear branch y commitear los cambios:

```bash
git checkout -b fix/pagos-monto-ciclo
git add apps/pagos/tasks.py apps/pagos/tests/test_tasks.py
git commit -m "Fix: seleccionar monto según ciclo + fallback precio_pagado; agregar tests"
```

2. Ejecutar tests:

```bash
pytest apps/pagos/tests/test_tasks.py -q
```
