# Integración POS ↔ API (Sandbox)

Guía paso a paso para exponer la API y conectar POS usando **API Keys con prefijo RNC**.

---

## 1) Objetivo

Conectar los POS con la API para consumir endpoints de facturación electrónica y recursos relacionados.
Esta guía cubre **sandbox**, **autenticación Api‑Key**, **flujo de pruebas** y **recomendaciones de implementación en POS**.

---

## 2) Datos base y estándares

### 2.1 Base URL (sandbox)

```
https://sandbox-derejfact.derejsoft.com/api/v1/
```

### 2.2 Autenticación (único método para POS)

Header obligatorio:

```
Authorization: Api-Key <token>
```

### 2.3 Formato de la API Key

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
- La API **solo acepta Api-Key** (no JWT ni Bearer para POS).

---

## 3) Roles y autenticación

| Actor | Autenticación | Header | Uso |
| --- | --- | --- | --- |
| SUPERADMIN (humano) | JWT | `Authorization: Bearer <JWT>` | CRUD completo |
| ADMIN_EMPRESA (humano) | JWT | `Authorization: Bearer <JWT>` | Lectura + admin de su empresa |
| POS (sistema) | API Key | `Authorization: Api-Key <token>` | Solo lectura + emisión |

**Regla fija:**  
- Humanos → JWT.  
- POS → API Key.  
- API Key NO se usa para panel/admin.

---

## 4) Requisitos previos

### 4.1 Dominio y TLS

- Subdominio: `sandbox-derejfact.derejsoft.com`
- Certificado TLS válido (HTTPS obligatorio)

### 4.2 Datos mínimos por empresa

Para que un POS opere necesitas:

- Empresa creada
- Certificado .p12 cargado en almacenamiento externo (MinIO/S3)
- Plan/suscripción activa
- Paquetes de comprobantes activos (si aplica)
- API Key activa

### 4.3 Seguridad del certificado .p12

- El archivo .p12 **nunca se guarda en la base de datos**.
- Solo se guarda una `storage_key` que apunta al archivo en MinIO/S3.
- El **PIN del .p12 nunca se persiste** — viaja en el request y se usa en memoria.

---

## 5) Flujo de provisión de empresas (paso a paso)

### Paso 1 — Crear empresa

```
POST /api/v1/empresas/
```

Requiere JWT (SUPERADMIN).

### Paso 1b — Login para SUPERADMIN

```
POST /api/v1/auth/login/
Body: { "username": "...", "password": "..." }
Response: { "access": "<JWT>", "refresh": "<refresh_token>" }
```

Usar el token JWT obtenido como:

```
Authorization: Bearer <access_token>
```

Requiere JWT (SUPERADMIN).

### Paso 2 — Cargar certificado .p12

Subir el archivo .p12 al almacenamiento externo (MinIO/S3).  
En la empresa se guarda la `certificado_storage_key` (referencia al archivo).  
El **PIN nunca se guarda** — el POS lo envía en el body de cada request de emisión.

### Paso 3 — Crear plan (si no existe)

```
POST /api/v1/planes/
```

### Paso 4 — Crear suscripción

```
POST /api/v1/suscripciones/
```

### Paso 5 — Crear paquetes (si aplica)

```
POST /api/v1/paquetes/
```

### Paso 6 — Crear API Key

```
POST /api/v1/api-keys/
```

- Se genera token `rnc_<token>`
- **Guardar el token completo** en el POS (solo se devuelve una vez)

---

## 6) Whitelist de IPs (opcional)

**Regla:**

- Si `allowed_ips` está vacío → acceso permitido desde cualquier IP
- Si tiene IPs → debe cumplirse

Errores:

- 403: "IP no autorizada para esta API Key"

---

## 7) Rotación de API Keys (manual con auditoría)

- Acción disponible: `POST /api/v1/api-keys/{id}/rotar/`
- Revoca la key anterior y genera una nueva
- Debe registrarse:
  - usuario que la rotó
  - fecha
  - motivo (opcional)

**Recomendación para POS:**

- Permitir "Regenerar Key" en el panel
- Mostrarla una sola vez y pedir confirmación

---

## 8) Implementación en POS (cliente REST JSON)

### 8.1 Guardar credenciales

Guardar en `.env`:

```
DEREJ_API_KEY=131793916_x8f9k3...
DEREJ_API_BASE=https://sandbox-derejfact.derejsoft.com/api/v1/
```

### 8.2 Cliente HTTP

- Timeout recomendado: 10s
- Reintentos: 2–3 en 5xx
- Headers:

  ```
  Authorization: Api-Key <token>
  Content-Type: application/json
  ```

### 8.3 .p12 PIN en emisión

Cuando el endpoint de emisión esté disponible, el POS debe enviar:

```json
{
  "cert_pin": "1234",
  "comprobante": { ... }
}
```

- El **PIN** es la contraseña del certificado .p12 de la empresa.
- El PIN **nunca se guarda** — solo se usa en memoria para firmar el XML.
- El archivo .p12 ya está almacenado en la infraestructura (no se envía).

### 8.4 Errores comunes

| Código | Motivo |
|--------|--------|
| 401 | API Key inválida o expirada |
| 403 | IP no autorizada |
| 404 | Recurso no encontrado |
| 429 | Rate limit |
| 5xx | Error interno de API |

---

## 9) Pruebas con Postman (paso a paso)

### Paso 1 — Verificar la API Key

```
GET /api/v1/empresas/
Authorization: Api-Key <token>
```

### Paso 2 — Probar whitelist (si aplica)

- Llamar desde IP autorizada → 200
- Llamar desde IP no autorizada → 403

### Paso 3 — Consultar secuenciales

```
GET /api/v1/secuenciales/
```

### Paso 4 — Preview de NCF

```
GET /api/v1/secuenciales/{id}/preview/
```

---

## 10) Endpoints mínimos recomendados para POS (sandbox)

### Lectura (Api-Key)

- `GET /api/v1/secuenciales/`
- `GET /api/v1/secuenciales/{id}/preview/`
- `GET /api/v1/empresas/{id}/comprobantes/`
- `GET /api/v1/empresas/{id}/suscripcion/`
- `GET /api/v1/pagos/historial/?empresa={id}` — historial de pagos de la empresa

### Emisión (Api-Key + PIN .p12)

Cuando estén disponibles:

| Método | Endpoint | Body adicional |
|--------|----------|----------------|
| POST | /api/v1/comprobantes/emitir/ | `{ "cert_pin": "...", "comprobante": {...} }` |

---

## 11) Checklist final (antes de habilitar a un POS)

- [ ] Empresa creada
- [ ] Certificado .p12 cargado en almacenamiento externo
- [ ] Suscripción activa
- [ ] Paquetes activos
- [ ] API Key generada con prefijo RNC
- [ ] API Key entregada al POS
- [ ] (Opcional) IPs permitidas cargadas
- [ ] Pruebas con Postman OK (lectura + emisión)

---

## 12) Consumo desde Frontend (JWT)

Guía para aplicaciones web/panel administrativo que consumen la API usando autenticación JWT.

### 12.1 Autenticación

```
POST /api/v1/auth/login/
Content-Type: application/json

{
  "username": "admin@ejemplo.com",
  "password": "********"
}

Response 200:
{
  "access": "eyJhbGciOiJI...",
  "refresh": "eyJhbGciOiJSUzI1..."
}
```

### 12.2 Uso del token

Incluir en todos los requests:

```
Authorization: Bearer eyJhbGciOiJI...
```

### 12.3 Refrescar token

Cuando el `access_token` expire:

```
POST /api/v1/auth/token/refresh/
Content-Type: application/json

{
  "refresh": "eyJhbGciOiJSUzI1..."
}

Response 200:
{
  "access": "eyJhbGciOiJSUzI1..."
}
```

### 12.4 Interceptor recomendado (axios)

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'https://sandbox-derejfact.derejsoft.com/api/v1/',
});

// Interceptor para agregar JWT
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Interceptor para refrescar token en 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) {
        try {
          const { data } = await axios.post(
            'https://sandbox-derejfact.derejsoft.com/api/v1/auth/token/refresh/',
            { refresh }
          );
          localStorage.setItem('access_token', data.access);
          error.config.headers.Authorization = `Bearer ${data.access}`;
          return api(error.config);
        } catch {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);
```

### 12.5 Endpoints de panel (JWT requerido)

| Método | Ruta | Uso |
|--------|------|-----|
| GET/POST | `/api/v1/usuarios/` | CRUD usuarios (SUPERADMIN) |
| GET/PUT/PATCH | `/api/v1/usuarios/me/` | Perfil propio |
| POST | `/api/v1/usuarios/me/change-password/` | Cambiar contraseña propia |
| GET/POST | `/api/v1/empresas/` | CRUD empresas |
| GET/POST | `/api/v1/planes/` | CRUD planes |
| GET/POST | `/api/v1/suscripciones/` | CRUD suscripciones |
| GET/POST | `/api/v1/paquetes/` | CRUD paquetes |
| GET/POST | `/api/v1/pagos/` | CRUD pagos |
| POST | `/api/v1/pagos/{id}/confirmar/` | Confirmar pago |
| POST | `/api/v1/pagos/{id}/rechazar/` | Rechazar pago |
| GET | `/api/v1/pagos/historial/` | Historial de pagos |
| GET/POST | `/api/v1/api-keys/` | CRUD API Keys |
| POST | `/api/v1/api-keys/{id}/revocar/` | Revocar key |
| POST | `/api/v1/api-keys/{id}/rotar/` | Rotar key |
| GET/POST | `/api/v1/secuenciales/` | CRUD secuenciales |
| POST | `/api/v1/secuenciales/{id}/bloquear/` | Bloquear secuencial |
| POST | `/api/v1/secuenciales/{id}/desbloquear/` | Desbloquear secuencial |

### 12.6 Roles y alcance

| Rol | Acceso |
|-----|--------|
| SUPERADMIN | Todos los endpoints CRUD |
| ADMIN_EMPRESA | Lectura + escritura limitada a su empresa |
| USUARIO_EMPRESA | Solo su perfil (`/usuarios/me/`) |

### 12.7 Buenas prácticas Frontend

- Guardar tokens en `localStorage` o `HttpOnly cookies`
- Implementar interceptor de refresh automático
- Redirigir a login en 401 si el refresh falla
- No exponer API Keys en código frontend
- Usar variables de entorno para la base URL

---

## 13) Buenas prácticas generales

- No exponer la API Key en front-end público
- Rotar manualmente si sospecha de compromiso
- El PIN del .p12 debe viajar cifrado (TLS) — nunca en texto plano por canales no seguros
- Revisar consumo y logs periódicamente
- Humanos → JWT. POS → API Key (nunca mezclar)
