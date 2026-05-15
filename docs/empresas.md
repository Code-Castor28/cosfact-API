# Empresas

Documentacion de endpoints para gestion de empresas (tenants del SaaS).

## Autenticacion

Soporta dos tipos de autenticación:

| Tipo | Header | Usuario |
| --- | --- | --- |
| JWT (Admin) | `Authorization: Bearer <JWT>` | SUPERADMIN / ADMIN_EMPRESA |
| API Key (POS) | `Authorization: Api-Key <token>` | Empresa (solo lectura) |

- SUPERADMIN: CRUD completo sobre cualquier empresa.
- ADMIN_EMPRESA (JWT): solo lectura de su propia empresa.
- Empresa (Api-Key): solo lectura de su propia empresa.
- USUARIO_EMPRESA: sin acceso a este modulo.

## Endpoints

Resumen rapido:

| Metodo | Ruta | Descripcion | Permisos |
| --- | --- | --- | --- |
| GET | /api/v1/empresas/ | Listar empresas | SUPERADMIN / Admin empresa / Empresa (Api-Key) |
| POST | /api/v1/empresas/ | Crear empresa | SUPERADMIN |
| GET | /api/v1/empresas/{id}/ | Ver empresa | SUPERADMIN / Admin empresa / Empresa (Api-Key) |
| PATCH | /api/v1/empresas/{id}/ | Actualizar empresa | SUPERADMIN |
| DELETE | /api/v1/empresas/{id}/ | Eliminar (soft) | SUPERADMIN |
| GET | /api/v1/empresas/{id}/suscripcion/ | Suscripcion activa | SUPERADMIN / Admin empresa / Empresa (Api-Key) |
| GET | /api/v1/empresas/{id}/comprobantes/ | Paquetes de comprobantes | SUPERADMIN / Admin empresa / Empresa (Api-Key) |

---

## CRUD de Empresas

### Listar empresas

`GET /api/v1/empresas/`

Parametros opcionales:

| Parametro | Tipo | Descripcion |
| --- | --- | --- |
| incluir_eliminadas | boolean | Incluir soft-deleted (solo SUPERADMIN) |

Respuesta 200:
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
      "rnc": "131793916",
      "razon_social": "Empresa de Prueba SRL",
      "nombre_comercial": "amigostodos",
      "ambiente": "testecf",
      "estado": "PENDIENTE_CERTIFICADO",
      "activa": true,
      "creado_at": "2026-05-08T05:07:06.923444Z"
    }
  ]
}
```

Campos del listado (EmpresaListSerializer):
- `id`, `rnc`, `razon_social`, `nombre_comercial`
- `ambiente`, `estado`, `activa`, `creado_at`

### Crear empresa

`POST /api/v1/empresas/`

Body (JSON):
```json
{
  "rnc": "131793916",
  "razon_social": "Empresa de Prueba SRL",
  "nombre_comercial": "amigostodos",
  "ambiente": "testecf",
  "estado": "PENDIENTE_CERTIFICADO",
  "activa": true
}
```

Campos del body:

| Campo | Tipo | Requerido | Descripcion |
| --- | --- | --- | --- |
| rnc | string | Si | RNC (9 u 11 digitos) |
| razon_social | string | Si | Razon social |
| nombre_comercial | string | No | Nombre comercial |
| ambiente | string | No | testecf, certecf, ecf |
| estado | string | No | ACTIVA, SUSPENDIDA, CANCELADA, PENDIENTE_CERTIFICADO |
| activa | boolean | No | Estado operativo |

Respuesta 201: detalle de la empresa creada.

### Ver detalle

`GET /api/v1/empresas/{id}/`

Respuesta 200 (SUPERADMIN):
```json
{
  "id": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
  "rnc": "131793916",
  "razon_social": "Empresa de Prueba SRL",
  "nombre_comercial": "amigostodos",
  "ambiente": "testecf",
  "estado": "PENDIENTE_CERTIFICADO",
  "activa": true,
  "certificado_hash": "",
  "certificado_vence_at": null,
  "certificado_vence_pronto": false,
  "deleted_at": null,
  "creado_at": "2026-05-08T05:07:06.923444Z",
  "actualizado_at": "2026-05-14T23:09:06.470673Z"
}
```

Respuesta 200 (Admin empresa):
```json
{
  "id": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
  "rnc": "131793916",
  "razon_social": "Empresa de Prueba SRL",
  "nombre_comercial": "amigostodos",
  "ambiente": "testecf",
  "estado": "PENDIENTE_CERTIFICADO",
  "activa": true,
  "certificado_vence_at": null,
  "certificado_vence_pronto": false,
  "creado_at": "2026-05-08T05:07:06.923444Z"
}
```

Nota: Admin empresa y Empresa (Api-Key) ven los mismos campos limitados (sin `certificado_hash`, `deleted_at`, `actualizado_at`).

### Actualizar

`PATCH /api/v1/empresas/{id}/`

Body parcial:
```json
{
  "nombre_comercial": "Nuevo nombre",
  "ambiente": "certecf"
}
```

Respuesta 200: detalle actualizado.

### Eliminar (soft delete)

`DELETE /api/v1/empresas/{id}/`

No borra fisicamente. Marca `deleted_at` y `activa = False`.

Respuesta 204: sin contenido.

---

## Endpoints de Suscripcion y Comprobantes

### Suscripcion activa

`GET /api/v1/empresas/{id}/suscripcion/`

Devuelve la suscripcion activa mas reciente de la empresa.

Respuesta 200:
```json
{
  "id": "c9381df2-874f-4c86-9e54-44b02d2a8910",
  "plan_detalle": {
    "nombre": "Basico",
    "limite_comprobantes": 10,
    "ciclo_disponible": "MENSUAL"
  },
  "ciclo": "MENSUAL",
  "estado": "ACTIVA",
  "fecha_inicio": "2026-05-01",
  "fecha_renovacion": "2026-06-01",
  "precio_pagado": "200.00",
  "esta_activa": true,
  "creado_at": "2026-05-08T05:10:26.271409Z"
}
```

Respuesta 404 si no tiene suscripcion activa.

### Paquetes de comprobantes

`GET /api/v1/empresas/{id}/comprobantes/`

Devuelve los paquetes activos (orden FIFO por fecha de compra).

Respuesta 200:
```json
{
  "empresa_id": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
  "empresa_rnc": "131793916",
  "total_paquetes_activos": 1,
  "paquetes": [
    {
      "id": "a7b3c2d1-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
      "total_comprobantes": 500,
      "comprobantes_usados": 0,
      "comprobantes_restantes": 500,
      "estado": "ACTIVO",
      "origen": "SUSCRIPCION",
      "fecha_vencimiento": null,
      "disponible": true,
      "fecha_compra": "2026-05-08T05:10:26.271409Z"
    }
  ]
}
```

---

## Modelo de Datos

### Empresa

| Campo | Tipo | Descripcion |
| --- | --- | --- |
| id | UUID | Identificador unico |
| rnc | string(11) | RNC unico |
| razon_social | string(255) | Razon social |
| nombre_comercial | string(255) | Nombre comercial |
| ambiente | string | testecf / certecf / ecf |
| estado | string | ACTIVA / SUSPENDIDA / CANCELADA / PENDIENTE_CERTIFICADO |
| activa | boolean | Estado operativo |
| certificado_storage_key | string | Referencia al .p12 en S3 (nunca el archivo) |
| certificado_hash | string | SHA-256 del .p12 |
| certificado_vence_at | date | Fecha de vencimiento del certificado |
| deleted_at | datetime | Soft delete |
| creado_at | datetime | Fecha de creacion |
| actualizado_at | datetime | Ultima actualizacion |

### Ambientes

| Valor | Descripcion |
| --- | --- |
| testecf | Desarrollo / Test |
| certecf | Certificacion |
| ecf | Produccion |

### Estados

| Valor | Descripcion |
| --- | --- |
| ACTIVA | Operando normalmente |
| SUSPENDIDA | Suspendida temporalmente |
| CANCELADA | Dado de baja |
| PENDIENTE_CERTIFICADO | Esperando certificado digital |

## Errores comunes

| Codigo | Motivo |
| --- | --- |
| 400 | RNC invalido, datos incorrectos |
| 401 | JWT ausente o invalido; o API Key invalida |
| 403 | Sin permisos para la empresa, IP no autorizada |
| 404 | Empresa no encontrada |
