# QA - Pagos

Fecha: 22 de mayo de 2026

## Alcance
- Endpoints de pagos segun docs/contexto_pago.md
- Implementacion actual en apps/pagos

## Metodologia
- Revision estatica de codigo y documentos
- Pruebas manuales con curl contra http://127.0.0.1:8000/api/v1/

## Resultados de pruebas manuales
- GET /api/v1/pagos/ -> 200 OK (lista vacia)
- GET /api/v1/pagos/historial/ -> 200 OK (sin validar contenido por no haber datos)

## Hallazgos

### Critico
1) Periodo de diciembre calcula fecha_inicio incorrecta
- Codigo: en confirmacion de pago, cuando periodo_mes == 12 se usa 1 de enero del mismo ano.
- Esperado: 1 de diciembre del mismo ano.
- Impacto: la suscripcion queda con fecha_inicio incorrecta para pagos de diciembre.

### Alto
3) Endpoint historial no permite API Key
- Docs: historial permite SUPERADMIN y API Key.
- Codigo: PagoViewSet usa IsSuperAdmin para todo el viewset.
- Impacto: integraciones con API Key no pueden consultar historial.

4) POST /api/v1/pagos/ deshabilitado (doc desactualizada)
- Docs: CRUD completo (incluye POST).
- Codigo: create() retorna 405 con mensaje de que los pagos son automaticos.
- Impacto: comportamiento distinto a la documentacion y posible bloqueo de QA.

### Medio
5) Ruta recomendada para confirmar no documentada
- Docs: confirmar via POST /api/v1/pagos/{id}/confirmar/
- Codigo: se recomienda PATCH /actualizar_confirmacion/ y confirmar() esta deprecado.
- Impacto: consumidores pueden seguir usando endpoint deprecado.

6) Campo metodo_pago puede quedar vacio fuera de choices
- Tasks: crea pagos con metodo_pago = '' para pendientes.
- Modelo: metodo_pago es requerido y con choices (sin blank/null).
- Impacto: data inconsistente; validaciones de DRF pueden fallar si se expone en create/patch.

### Bajo
7) Faltan pruebas automatizadas en app pagos
- No existe apps/pagos/tests.py en el repo.
- Impacto: cambios en logica de pagos no estan cubiertos por tests.

## Recomendaciones
- Corregir fecha_inicio para periodo diciembre en confirmacion.
- Ajustar permisos del endpoint historial segun doc (o actualizar doc si no aplica).
- Alinear docs con el flujo actual (create deshabilitado, usar actualizar_confirmacion).
- Definir formalmente el manejo de metodo_pago en PENDIENTE (permitir blank/null o default valido).
- Agregar tests unitarios para: confirmacion, duplicados por periodo, historial, permisos.

## Pendiente para QA en ambiente
- Probar confirmacion y rechazo con un pago real (se requiere data de prueba).
