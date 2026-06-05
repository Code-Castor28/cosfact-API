# Users

Documentacion de endpoints para gestion de usuarios y autenticacion.

## Autenticacion

- Login: `POST /api/v1/users/login/` — no requiere JWT.
- El resto de endpoints requieren JWT en header `Authorization: Bearer <JWT>`.
- SUPERADMIN: CRUD completo sobre cualquier usuario.
- ADMIN_EMPRESA: solo ve y edita usuarios de su propia empresa.
- USUARIO_EMPRESA: solo accede a `/me/` y `/me/change-password/`.

## Endpoints

Resumen rapido:

| Metodo | Ruta | Descripcion | Permisos |
| --- | --- | --- | --- |
| POST | /api/v1/users/login/ | Obtener JWT | Publico |
| POST | /api/v1/users/token/refresh/ | Refrescar JWT | Publico |
| POST | /api/v1/users/recover-password/ | Recuperar contrasena | Publico |
| GET | /api/v1/users/ | Listar usuarios | SUPERADMIN / Admin empresa |
| POST | /api/v1/users/ | Crear usuario | SUPERADMIN |
| GET | /api/v1/users/{id}/ | Ver usuario | SUPERADMIN / Admin empresa |
| PUT/PATCH | /api/v1/users/{id}/ | Actualizar usuario | SUPERADMIN / Admin empresa |
| DELETE | /api/v1/users/{id}/ | Desactivar usuario | SUPERADMIN |
| GET | /api/v1/users/me/ | Perfil propio | Autenticado |
| PUT/PATCH | /api/v1/users/me/ | Actualizar perfil propio | Autenticado |
| POST | /api/v1/users/me/change-password/ | Cambiar contrasena | Autenticado |

---

## Autenticacion JWT

### Login

`POST /api/v1/users/login/`

Body (JSON):
```json
{
  "email": "derej@gmail.com",
  "password": "admin123"
}
```

Respuesta 200:
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIs...",
  "access": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Refresh token

`POST /api/v1/users/token/refresh/`

Body:
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIs..."
}
```

Respuesta 200:
```json
{
  "access": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

## CRUD de Usuarios

### Listar usuarios

`GET /api/v1/users/`

Respuesta 200:
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "8215de01-1f31-4130-9e1b-da518df05b6a",
      "email": "derej@gmail.com",
      "nombre": "pope",
      "apellido": "poder",
      "rol": "SUPERADMIN",
      "empresa": null,
      "empresa_detalle": null,
      "is_active": true,
      "creado_at": "2026-05-08T05:00:32.465164Z"
    }
  ]
}
```

Campos adicionales visibles solo para SUPERADMIN:
- `intentos_fallidos`
- `bloqueado_hasta`
- `ultimo_login_ip`

Filtros por empresa (segun el rol):
- SUPERADMIN: todos los usuarios.
- ADMIN_EMPRESA: solo usuarios de su misma empresa.

### Crear usuario

`POST /api/v1/users/`

Body (JSON):
```json
{
  "email": "nuevo@empresa.com",
  "nombre": "Juan",
  "apellido": "Perez",
  "password": "TempPass123",
  "rol": "ADMIN_EMPRESA",
  "empresa": "4716d836-4fc4-4d6a-ad52-3c9ba13dbcb0"
}
```

Campos del body:

| Campo | Tipo | Requerido | Descripcion |
| --- | --- | --- | --- |
| email | string | Si | Email unico |
| nombre | string | Si | Nombre |
| apellido | string | Si | Apellido |
| password | string | No* | Si no se envia, no tendra contrasena |
| rol | string | No | SUPERADMIN, ADMIN_EMPRESA, USUARIO_EMPRESA |
| empresa | UUID | No* | Requerido si rol no es SUPERADMIN |

Reglas de validacion:
- SUPERADMIN no puede tener empresa.
- No-SUPERADMIN debe tener empresa.

Respuesta 201: detalle del usuario creado.

### Ver detalle

`GET /api/v1/users/{id}/`

Respuesta 200: detalle del usuario.

### Actualizar

`PUT /api/v1/users/{id}/`

`PATCH /api/v1/users/{id}/`

Body parcial:
```json
{
  "nombre": "Nuevo Nombre",
  "password": "NuevaPass123"
}
```

Respuesta 200: detalle actualizado.

### Desactivar (soft delete)

`DELETE /api/v1/users/{id}/`

No borra fisicamente. Marca `is_active = False`.

Respuesta 204: sin contenido.

---

## Perfil propio

### Ver perfil

`GET /api/v1/users/me/`

Respuesta 200: detalle del usuario autenticado.

### Actualizar perfil

`PUT /api/v1/users/me/`

`PATCH /api/v1/users/me/`

Campos protegidos (no se pueden cambiar via `/me/`):
- `rol`
- `empresa`
- `is_active`
- `email`

Body ejemplo:
```json
{
  "nombre": "Nuevo Nombre"
}
```

Respuesta 200: perfil actualizado.

### Cambiar contrasena

`POST /api/v1/users/me/change-password/`

Body:
```json
{
  "password_actual": "miPassActual",
  "password_nueva": "miNuevaPass123"
}
```

Respuesta 200:
```json
{
  "status": "Contrasena actualizada exitosamente"
}
```

---

## Recuperacion de contrasena

`POST /api/v1/users/recover-password/`

Body:
```json
{
  "email": "derej@gmail.com"
}
```

Respuesta 200 (solo desarrollo):
```json
{
  "mensaje": "Recuperacion simulada. En el futuro esto enviara un email.",
  "email": "derej@gmail.com",
  "temp_password": "AbCd1234XyZz"
}
```

En produccion enviara un email. En desarrollo devuelve la contrasena temporal.

---

## Roles

| Rol | Descripcion | Acceso |
| --- | --- | --- |
| SUPERADMIN | Administrador global | CRUD todos los usuarios, todas las empresas |
| ADMIN_EMPRESA | Admin de una empresa | Ver/editar usuarios de su empresa |
| USUARIO_EMPRESA | Usuario regular | Solo su perfil |

## Errores comunes

| Codigo | Motivo |
| --- | --- |
| 400 | Datos invalidos, contrasena incorrecta |
| 401 | JWT ausente, invalido o expirado |
| 403 | Sin permisos para la accion |
| 404 | Usuario no encontrado |
