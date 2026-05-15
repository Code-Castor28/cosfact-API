# API Keys

Documentacion de endpoints para administrar API keys (solo SUPERADMIN via JWT).

## Dos roles

| Rol | Autenticación | Acceso |
| --- | --- | --- |
| **Admin (SUPERADMIN)** | `Authorization: Bearer <JWT>` | CRUD completo sobre API Keys |
| **POS (Empresa)** | `Authorization: Api-Key <token>` | Solo consume endpoints (lectura) |

## Formato de la API Key

```
<rnc>_<token>
```

Ejemplo:

```
131793916_x8f9k3abcdef...
```

**Reglas:**

- El **RNC va sin guiones**.
- El token es aleatorio (mín. 32 caracteres recomendado).
- El token completo **solo se muestra una vez** al crearlo o rotarlo.
- La API **solo acepta Api-Key** para POS (no JWT ni Bearer).

## Autenticacion para administrar keys

- Requiere JWT en header `Authorization: Bearer <JWT>`.
- Solo usuarios con rol `SUPERADMIN`.

## Endpoints

Resumen rapido:

| Metodo | Ruta | Descripcion | Body | Retorna token |
| --- | --- | --- | --- | --- |
| GET | /api/v1/api-keys/ | Listar API keys | No | No |
| POST | /api/v1/api-keys/ | Crear API key | Si | Si (solo una vez) |
| GET | /api/v1/api-keys/{id}/ | Ver detalle | No | No |
| PATCH | /api/v1/api-keys/{id}/ | Actualizar | Si | No |
| PUT | /api/v1/api-keys/{id}/ | Reemplazar | Si | No |
| DELETE | /api/v1/api-keys/{id}/ | Revocar | Opcional | No |
| POST | /api/v1/api-keys/{id}/revocar/ | Revocar | Opcional | No |
| POST | /api/v1/api-keys/{id}/rotar/ | Rotar | Opcional | Si (solo una vez) |

### Listar API keys

`GET /api/v1/api-keys/`

Filtros (query params opcionales):

| Parametro | Tipo | Ejemplo | Descripcion |
| --- | --- | --- | --- |
| empresa | UUID | 4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0 | Filtra por empresa |
| activa | boolean | true | Solo activas o inactivas |
| expirada | boolean | true | Solo expiradas o no expiradas |
| prefix | string | 131793916 | Busca por prefijo (RNC) |
| nombre | string | POS | Busca por nombre |

Ejemplo:
```
GET /api/v1/api-keys/?empresa=4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0&activa=true&prefix=131793916
```

Respuesta 200 (ejemplo):
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "63639ab1-48bc-4db4-9b2e-5d88242075eb",
      "empresa": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
      "empresa_detalle": {
        "id": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
        "razon_social": "Empresa de Prueba SRL",
        "rnc": "131793916"
      },
      "nombre": "POS Sucursal Norte",
      "prefix": "131793916",
      "scopes": ["comprobantes:crear", "comprobantes:consultar"],
      "allowed_ips": [],
      "rate_limit_cantidad": 100,
      "rate_limit_ventana": "HOUR",
      "activa": true,
      "expira_at": null,
      "revocado_at": null,
      "revocado_por": null,
      "revocado_motivo": "",
      "ultimo_uso_at": null,
      "ultimo_uso_ip": null,
      "creado_at": "2026-05-12T17:14:34.815379Z",
      "actualizado_at": "2026-05-12T17:14:34.815379Z"
    }
  ]
}
```

### Crear API key

`POST /api/v1/api-keys/`

Body (JSON):
```json
{
  "empresa": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
  "nombre": "POS Sucursal Norte",
  "scopes": ["comprobantes:crear", "comprobantes:consultar"],
  "allowed_ips": [],
  "rate_limit_cantidad": 100,
  "rate_limit_ventana": "HOUR",
  "expira_at": null,
  "activa": true
}
```

Campos del body:

| Campo | Tipo | Requerido | Descripcion |
| --- | --- | --- | --- |
| empresa | UUID | Si | Empresa dueña de la API key |
| nombre | string | Si | Nombre descriptivo |
| scopes | list[string] | No | Permisos de la API key |
| allowed_ips | list[string] | No | IPs o CIDRs permitidos |
| rate_limit_cantidad | int | No | Limite de requests |
| rate_limit_ventana | string | No | MINUTE, HOUR, DAY |
| expira_at | datetime | No | Fecha de expiracion |
| activa | boolean | No | Estado de la key |

Respuesta 201 (ejemplo):
```json
{
  "id": "63639ab1-48bc-4db4-9b2e-5d88242075eb",
  "empresa": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
  "empresa_detalle": {
    "id": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
    "razon_social": "Empresa de Prueba SRL",
    "rnc": "131793916"
  },
  "nombre": "POS Sucursal Norte",
  "prefix": "131793916",
  "scopes": ["comprobantes:crear", "comprobantes:consultar"],
  "allowed_ips": [],
  "rate_limit_cantidad": 100,
  "rate_limit_ventana": "HOUR",
  "activa": true,
  "expira_at": null,
  "revocado_at": null,
  "revocado_por": null,
  "revocado_motivo": "",
  "ultimo_uso_at": null,
  "ultimo_uso_ip": null,
  "creado_at": "2026-05-12T17:14:34.815379Z",
  "actualizado_at": "2026-05-12T17:14:34.815379Z",
  "token": "131793916_5GDko-1zaNQzhwsJTMzOmMekYbph50kNe6PG3vR-UEA"
}
```

Nota: el campo `token` solo se devuelve una vez en la creacion.

### Ver detalle

`GET /api/v1/api-keys/{id}/`

Respuesta 200: igual a la lista, sin `token`.

### Actualizar

`PATCH /api/v1/api-keys/{id}/`

Body (JSON) ejemplo:
```json
{
  "nombre": "POS Sucursal Norte - Caja 2",
  "activa": true
}
```

Respuesta 200: detalle actualizado.

### Revocar

`POST /api/v1/api-keys/{id}/revocar/`

Body (JSON) opcional:
```json
{
  "motivo": "Comprometida"
}
```

Respuesta 200: detalle de la key revocada.

### Eliminar (revocar)

`DELETE /api/v1/api-keys/{id}/`

Respuesta 204: sin contenido. La key queda revocada.

### Rotar

`POST /api/v1/api-keys/{id}/rotar/`

Body (JSON) opcional:
```json
{
  "nombre": "POS Sucursal Norte (rotada)"
}
```

Respuesta 201 (ejemplo):
```json
{
  "id": "b3a6b8a1-52e8-40c6-8b89-1f17c2e9db1e",
  "empresa": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
  "empresa_detalle": {
    "id": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
    "razon_social": "Empresa de Prueba SRL",
    "rnc": "131793916"
  },
  "nombre": "POS Sucursal Norte (rotada)",
  "prefix": "131793916",
  "scopes": ["comprobantes:crear", "comprobantes:consultar"],
  "allowed_ips": [],
  "rate_limit_cantidad": 100,
  "rate_limit_ventana": "HOUR",
  "activa": true,
  "expira_at": null,
  "revocado_at": null,
  "revocado_por": null,
  "revocado_motivo": "",
  "ultimo_uso_at": null,
  "ultimo_uso_ip": null,
  "creado_at": "2026-05-12T17:20:12.000000Z",
  "actualizado_at": "2026-05-12T17:20:12.000000Z",
  "token": "131793916_x8f9k3...",
  "key_revocada_id": "63639ab1-48bc-4db4-9b2e-5d88242075eb"
}
```

## Scopes permitidos

| Scope | Descripcion |
| --- | --- |
| comprobantes:crear | Emitir comprobantes |
| comprobantes:consultar | Consultar comprobantes |
| comprobantes:anular | Anular comprobantes |
| secuenciales:consultar | Consultar secuenciales |

## Errores comunes

| Codigo | Motivo |
| --- | --- |
| 400 | Scopes invalidos |
| 401 | JWT ausente o invalido; o API Key invalida |
| 403 | Sin permisos (rol insuficiente, IP no autorizada) |
