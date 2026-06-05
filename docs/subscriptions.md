# Subscriptions

Documentacion de endpoints para planes, suscripciones y paquetes.

## Autenticacion

- JWT para SUPERADMIN y ADMIN_EMPRESA.
- API Key (empresa) puede leer sus recursos.

## Endpoints

Resumen rapido:

| Metodo | Ruta | Descripcion | Permisos |
| --- | --- | --- | --- |
| GET | /api/v1/subscriptions/planes/ | Listar planes | Publico autenticado |
| POST | /api/v1/subscriptions/planes/ | Crear plan | SUPERADMIN |
| GET | /api/v1/subscriptions/planes/{id}/ | Ver plan | Publico autenticado |
| PATCH/PUT | /api/v1/subscriptions/planes/{id}/ | Actualizar plan | SUPERADMIN |
| DELETE | /api/v1/subscriptions/planes/{id}/ | Eliminar plan | SUPERADMIN |
| GET | /api/v1/subscriptions/suscripciones/ | Listar suscripciones | SUPERADMIN / Admin empresa / Empresa(API key) |
| POST | /api/v1/subscriptions/suscripciones/ | Crear suscripcion | SUPERADMIN |
| GET | /api/v1/subscriptions/suscripciones/{id}/ | Ver suscripcion | Acceso por empresa |
| PATCH/PUT | /api/v1/subscriptions/suscripciones/{id}/ | Actualizar suscripcion | SUPERADMIN |
| DELETE | /api/v1/subscriptions/suscripciones/{id}/ | Eliminar suscripcion | SUPERADMIN |
| GET | /api/v1/subscriptions/paquetes/ | Listar paquetes | SUPERADMIN / Admin empresa / Empresa(API key) |
| POST | /api/v1/subscriptions/paquetes/ | Crear paquete | SUPERADMIN |
| GET | /api/v1/subscriptions/paquetes/{id}/ | Ver paquete | Acceso por empresa |
| PATCH/PUT | /api/v1/subscriptions/paquetes/{id}/ | Actualizar paquete | SUPERADMIN |
| DELETE | /api/v1/subscriptions/paquetes/{id}/ | Eliminar paquete | SUPERADMIN |

## Planes

### Crear plan

`POST /api/v1/subscriptions/planes/`

Body (JSON):
```json
{
  "nombre": "Plan Basico",
  "descripcion": "Hasta 500 comprobantes",
  "limite_comprobantes": 500,
  "precio_mensual": "1500.00",
  "precio_anual": "15000.00",
  "ciclo_disponible": "AMBOS",
  "tipos_ecf_permitidos": [31, 32, 41],
  "activo": true,
  "orden": 1
}
```

Campos:

| Campo | Tipo | Requerido | Descripcion |
| --- | --- | --- | --- |
| nombre | string | Si | Nombre del plan |
| descripcion | string | No | Descripcion corta |
| limite_comprobantes | int | Si | Cantidad incluida |
| precio_mensual | decimal | Si* | Requerido si ciclo incluye mensual |
| precio_anual | decimal | Si* | Requerido si ciclo incluye anual |
| ciclo_disponible | string | Si | MENSUAL, ANUAL, AMBOS |
| tipos_ecf_permitidos | list[int] | No | null = todos |
| activo | boolean | No | Estado del plan |
| orden | int | No | Orden de visualizacion |

### Listar planes

`GET /api/v1/subscriptions/planes/`

Notas:
- SUPERADMIN ve todos.
- Otros roles ven solo `activo=true`.

## Suscripciones

### Crear suscripcion

`POST /api/v1/subscriptions/suscripciones/`

Body (JSON):
```json
{
  "empresa": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
  "plan": "a3d2f2b1-1f8a-45e6-8a4b-2b71f5d901a1",
  "ciclo": "MENSUAL",
  "estado": "ACTIVA",
  "fecha_inicio": "2026-05-01",
  "fecha_renovacion": "2026-06-01",
  "precio_pagado": "1500.00"
}
```

Campos:

| Campo | Tipo | Requerido | Descripcion |
| --- | --- | --- | --- |
| empresa | UUID | Si | Empresa dueña |
| plan | UUID | Si | Plan asociado |
| ciclo | string | Si | MENSUAL o ANUAL |
| estado | string | No | ACTIVA, SUSPENDIDA, CANCELADA, VENCIDA |
| fecha_inicio | date | Si | Inicio del ciclo |
| fecha_renovacion | date | Si | Proxima renovacion |
| precio_pagado | decimal | No | Precio pagado |

## Paquetes

### Crear paquete

`POST /api/v1/subscriptions/paquetes/`

Body (JSON):
```json
{
  "empresa": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
  "suscripcion": "c9381df2-874f-4c86-9e54-44b02d2a8910",
  "plan": "a3d2f2b1-1f8a-45e6-8a4b-2b71f5d901a1",
  "total_comprobantes": 500,
  "comprobantes_usados": 0,
  "estado": "ACTIVO",
  "origen": "SUSCRIPCION",
  "fecha_vencimiento": null
}
```

Campos:

| Campo | Tipo | Requerido | Descripcion |
| --- | --- | --- | --- |
| empresa | UUID | Si | Empresa dueña |
| suscripcion | UUID | No | Suscripcion asociada |
| plan | UUID | Si | Plan asociado |
| total_comprobantes | int | Si | Total del paquete |
| comprobantes_usados | int | No | Inicialmente 0 |
| estado | string | No | ACTIVO, AGOTADO, VENCIDO, CANCELADO |
| origen | string | No | SUSCRIPCION o COMPRA_ADICIONAL |
| fecha_vencimiento | datetime | No | null = no vence |

## Respuestas

Las respuestas incluyen IDs y fechas en formato ISO 8601.

## Errores comunes

| Codigo | Motivo |
| --- | --- |
| 400 | Datos invalidos |
| 401 | JWT ausente o invalido |
| 403 | Sin permisos |
