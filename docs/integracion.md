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

## 3) Requisitos previos

### 3.1 Dominio y TLS

- Subdominio: `sandbox-derejfact.derejsoft.com`
- Certificado TLS válido (HTTPS obligatorio)

### 3.2 Datos mínimos por empresa

Para que un POS opere necesitas:

- Empresa creada
- Plan/suscripción activa
- Paquetes de comprobantes activos (si aplica)
- API Key activa

---

## 4) Flujo de provisión de empresas (paso a paso)

### Paso 1 — Crear empresa

```
POST /api/v1/empresas/
```

Requiere JWT (SUPERADMIN).

### Paso 2 — Crear plan (si no existe)

```
POST /api/v1/subscriptions/planes/
```

### Paso 3 — Crear suscripción

```
POST /api/v1/subscriptions/suscripciones/
```

### Paso 4 — Crear paquetes (si aplica)

```
POST /api/v1/subscriptions/paquetes/
```

### Paso 5 — Crear API Key

```
POST /api/v1/api-keys/
```

- Se genera token `rnc_<token>`
- **Guardar el token completo** en el POS (solo se devuelve una vez)

---

## 5) Whitelist de IPs (opcional)

**Regla:**

- Si `allowed_ips` está vacío → acceso permitido desde cualquier IP
- Si tiene IPs → debe cumplirse

Errores:

- 403: "IP no autorizada para esta API Key"

---

## 6) Rotación de API Keys (manual con auditoría)

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

## 7) Implementación en POS (cliente REST JSON)

### 7.1 Guardar credenciales

Guardar en `.env`:

```
DEREJ_API_KEY=131793916_x8f9k3...
DEREJ_API_BASE=https://sandbox-derejfact.derejsoft.com/api/v1/
```

### 7.2 Cliente HTTP

- Timeout recomendado: 10s
- Reintentos: 2–3 en 5xx
- Headers:

  ```
  Authorization: Api-Key <token>
  Content-Type: application/json
  ```

### 7.3 Errores comunes

| Código | Motivo |
|--------|--------|
| 401 | API Key inválida o expirada |
| 403 | IP no autorizada |
| 404 | Recurso no encontrado |
| 429 | Rate limit |
| 5xx | Error interno de API |

---

## 8) Pruebas con Postman (paso a paso)

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
GET /api/v1/sequences/
```

### Paso 4 — Preview de NCF

```
GET /api/v1/sequences/{id}/preview/
```

---

## 9) Endpoints mínimos recomendados para POS (sandbox)

- `GET /api/v1/sequences/`
- `GET /api/v1/sequences/{id}/preview/`
- `GET /api/v1/empresas/{id}/comprobantes/`
- `GET /api/v1/empresas/{id}/suscripcion/`

*(Cuando estén listos los endpoints de comprobantes, añadir: emitir, consultar, anular.)*

---

## 10) Checklist final (antes de habilitar a un POS)

- [ ] Empresa creada
- [ ] Suscripción activa
- [ ] Paquetes activos
- [ ] API Key generada con prefijo RNC
- [ ] API Key entregada al POS
- [ ] (Opcional) IPs permitidas cargadas
- [ ] Pruebas con Postman OK

---

## 11) Buenas prácticas

- No exponer la API Key en front-end público
- Rotar manualmente si sospecha de compromiso
- Revisar consumo y logs periódicamente
