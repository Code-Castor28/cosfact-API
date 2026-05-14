# Sequences

Documentacion de endpoints para secuenciales e-NCF.

## Autenticacion

- JWT para SUPERADMIN y ADMIN_EMPRESA.
- API Key (empresa) puede leer y hacer preview.

## Endpoints

Resumen rapido:

| Metodo | Ruta | Descripcion | Permisos |
| --- | --- | --- | --- |
| GET | /api/v1/sequences/ | Listar secuenciales | SUPERADMIN / Admin empresa / Empresa(API key) |
| POST | /api/v1/sequences/ | Crear secuencial | SUPERADMIN / Admin empresa |
| GET | /api/v1/sequences/{id}/ | Ver secuencial | Acceso por empresa |
| PATCH/PUT | /api/v1/sequences/{id}/ | Actualizar secuencial | SUPERADMIN / Admin empresa |
| DELETE | /api/v1/sequences/{id}/ | Eliminar secuencial | SUPERADMIN / Admin empresa |
| GET | /api/v1/sequences/{id}/preview/ | Preview e-NCF | SUPERADMIN / Admin empresa / Empresa(API key) |
| POST | /api/v1/sequences/{id}/bloquear/ | Bloquear secuencial | SUPERADMIN / Admin empresa |
| POST | /api/v1/sequences/{id}/desbloquear/ | Desbloquear secuencial | SUPERADMIN / Admin empresa |

## Secuenciales

### Crear secuencial

`POST /api/v1/sequences/`

Body (JSON):
```json
{
  "empresa": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0",
  "tipo_ecf": 31,
  "ultimo_numero": 0,
  "minimo_asignado": 1,
  "maximo_asignado": 9999999999,
  "bloqueado": false,
  "motivo_bloqueo": ""
}
```

Campos:

| Campo | Tipo | Requerido | Descripcion |
| --- | --- | --- | --- |
| empresa | UUID | Si | Empresa dueña |
| tipo_ecf | int | Si | Tipo e-CF (31, 32, 41, etc.) |
| ultimo_numero | int | No | Ultimo numero usado |
| minimo_asignado | int | No | Minimo del rango |
| maximo_asignado | int | No | Maximo del rango |
| bloqueado | boolean | No | Bloqueo manual |
| motivo_bloqueo | string | No | Motivo del bloqueo |

### Preview e-NCF

`GET /api/v1/sequences/{id}/preview/`

Respuesta 200 (ejemplo):
```json
{
  "proximo_encf": "E3100000001"
}
```

Formato: E + tipo(2 dígitos) + secuencial(10 dígitos) = 13 caracteres totales

### Bloquear

`POST /api/v1/sequences/{id}/bloquear/`

Body (JSON) opcional:
```json
{
  "motivo": "Rango en revision"
}
```

### Desbloquear

`POST /api/v1/sequences/{id}/desbloquear/`

Body vacio.

## Respuestas

El detalle de secuencial incluye:
- `proximo_encf` (solo preview, no consume)
- `porcentaje_uso`
- `casi_agotado`

## Errores comunes

| Codigo | Motivo |
| --- | --- |
| 400 | Datos invalidos |
| 401 | JWT ausente o invalido |
| 403 | Sin permisos |
