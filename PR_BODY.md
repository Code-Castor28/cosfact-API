Fix: seleccionar monto según ciclo + fallback precio_pagado; tests y logs diagnósticos

Descripción

Se corrige la lógica de selección y validación del `monto` en `apps/pagos/tasks.py` usado por la task `pagos.generar_pagos_automaticos`.

Problema

La task estaba intentando leer un atributo inexistente `plan.precio`, lo que hacía que `monto` siempre fuese `None`/`0` y la task saltara la creación de pagos para planes con precios válidos.

Cambios realizados

- Selección explícita del precio según `suscripcion.ciclo`: `precio_mensual` o `precio_anual`.
- Fallback a `suscripcion.precio_pagado` cuando el plan no tiene precio para el ciclo.
- Validación robusta con `Decimal(...) <= Decimal('0')` y manejo de conversiones inválidas.
- Logs temporales de diagnóstico añadidos para plan.nombre, plan.id, ciclo, precio_mensual, precio_anual, precio_pagado y monto seleccionado.
- Tests unitarios: `apps/pagos/tests/test_tasks.py` que cubren `MENSUAL` y `ANUAL`.

Resultados de test (local):

```
Ran 2 tests in 0.035s

OK
```

Instrucciones para reviewers / QA

1. Revisar cambios en `apps/pagos/tasks.py` y la lógica de fallback.
2. Ejecutar tests locales:

```bash
python manage.py test apps.pagos.tests.test_tasks --verbosity 2
```

3. Deploy a staging y ejecutar la task en staging. Verificar logs de Celery para entradas diagnósticas:

- `[PAGOS] Plan=<nombre> plan_id=<id> ciclo=<...> precio_mensual=... precio_anual=... precio_pagado_suscripcion=...`
- `[PAGOS] Precio seleccionado para Plan <id>: <monto>`

4. Confirmar que ya no aparece el warning:

- `[PAGOS] Plan <id> no tiene precio. Saltando ...`

5. Una vez validado en staging, quitar o degradar a `logger.debug` los logs de diagnóstico antes de merge final.

Comandos para crear branch y push (local):

```bash
git checkout -b fix/pagos-monto-ciclo
git add apps/pagos/tasks.py apps/pagos/tests/test_tasks.py apps/pagos/tests/__init__.py .github/PULL_REQUEST_TEMPLATE.md PR_BODY.md
git commit -m "Fix: seleccionar monto según ciclo + fallback precio_pagado; agregar tests y logs diagnósticos"
git push -u origin fix/pagos-monto-ciclo
```

Notas

- No ejecutar la task en producción hasta validar en staging. Los tests usan DB de prueba.
- Logs añadidos son temporales y deben eliminarse o bajarse a `debug` antes del merge.
