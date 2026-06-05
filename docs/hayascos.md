# Hallazgos: Arqui.md vs Implementación Real

> Fecha del análisis: 2 de junio de 2026  
> Actualización: 2 de junio de 2026 (revisión profunda de todo el código fuente; corrección hallazgo 10.6)
> Baseline: `docs/arqui.md` v1.0.0 (31 de mayo de 2026)

---

## 1. Stack Tecnológico

| Componente | Especificado | Implementado | Estado |
|:---|:---|:---|:---:|
| Framework | Django + DRF | Django 6.0.5 + DRF | ✅ |
| Base de datos | PostgreSQL | PostgreSQL (settings) | ✅ |
| Cola de tareas | Celery + Redis | Celery + Redis (settings) | ✅ |
| Criptografía | `cryptography` Fernet + PKCS#12 | `cryptography.fernet` + XMLSigner | ✅ |
| Almacenamiento XML | `FileSystemStorage` (`/var/www/derejfact/media/xmls/`) | `os.makedirs` + `open` a `/var/derejfact/xmls/` | ⚠️ Ruta distinta y no usa `FileSystemStorage` |
| Autenticación humana | JWT (`simplejwt`) | JWT (`simplejwt`) | ✅ |
| Autenticación POS | API Key (`ApiKeyAuthentication`) | `api_keys/authentication.py` | ✅ |
| Comunicación DGII | SOAP/XML | `dgii/utils/dgii_client.py` | ✅ |

---

## 2. Apps del Proyecto

| App (doc) | App (código) | Estado |
|:---|:---|:---|
| `usuarios` | `users` | ✅ Implementada |
| `empresas` | `empresas` | ✅ Implementada |
| `api-keys` | `api_keys` | ✅ Implementada |
| `suscripciones` | `subscriptions` | ⚠️ Nombre distinto |
| `secuencias` | `sequences` | ⚠️ Nombre distinto |
| `comprobantes` | `comprobantes` | ❌ Solo modelos. Serializers vacío (0 bytes), services vacío (0 bytes), vistas stub, URLs vacías |
| `dgii` | `dgii` | ⚠️ Servicios existen, vistas/urls vacíos (correcto según doc — solo interno) |
| `webhooks` | `webhooks` | ❌ Solo modelos. Serializers vacío (0 bytes), vistas stub, URLs vacías |
| `pagos` | `pagos` | ✅ Implementada |
| `notificaciones` | **❌ NO EXISTE** | ❌ App no creada |
| `auditoria` | `audit` | ⚠️ Solo modelos, middleware desactivado (comentado en settings) |
| *(no listada)* | `clientes` | ✅ Implementada |

---

## 3. Endpoints — Estado por App

### 3.1 Autenticación (`/api/v1/auth/`)

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `POST login/` | ✅ Activo | ✅ | ✅ |
| `POST token/refresh/` | ✅ Activo | ✅ | ✅ |
| `POST recover-password/` | ✅ Activo | ✅ | ✅ |

### 3.2 Usuarios

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `POST/GET /usuarios/` | ✅ | ✅ | ✅ |
| `GET/PATCH /usuarios/me/` | ✅ | ✅ | ✅ |
| `POST /usuarios/me/change-password/` | ✅ | ✅ | ✅ |

### 3.3 Empresas

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `POST/GET /empresas/` | ✅ | ✅ | ✅ |
| `GET /empresas/{id}/` | ✅ | ✅ | ✅ |
| `GET /empresas/{id}/suscripcion/` | ✅ | ✅ | ✅ |
| `GET /empresas/{id}/comprobantes/` | ✅ | ✅ | ✅ |

### 3.4 API Keys

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `POST/GET /api-keys/` | ✅ | ✅ | ✅ |
| `POST /api-keys/{id}/revocar/` | ✅ | ✅ | ✅ |
| `POST /api-keys/{id}/rotar/` | ✅ | ✅ | ✅ |

### 3.5 Planes / Suscripciones / Paquetes

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `POST/GET /planes/` | ✅ | ✅ | ✅ |
| `POST/GET /suscripciones/` | ✅ | ✅ | ✅ |
| `POST/GET /paquetes/` | ✅ | ✅ | ✅ |

### 3.6 Secuencias / Secuenciales

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `POST /secuencias/` (consolidado onboarding) | 🔧 Pendiente | ❌ No registrado en router | ❌ |
| `GET /secuenciales/` | ✅ | ✅ | ✅ |
| `GET /secuenciales/{id}/preview/` | ✅ | ✅ | ✅ |
| `POST /secuenciales/{id}/bloquear/` | ✅ | ✅ | ✅ |
| `POST /secuenciales/{id}/desbloquear/` | ✅ | ✅ | ✅ |

### 3.7 Comprobantes

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `POST /comprobantes/` | 🔧 Pendiente | ❌ Serializers vacío, services vacío, vistas stub | ❌ |
| `GET /comprobantes/` | 🔧 Pendiente | ❌ Vistas/URLs vacíos | ❌ |
| `GET /comprobantes/{id}/` | 🔧 Pendiente | ❌ Vistas/URLs vacíos | ❌ |
| `PATCH /comprobantes/{id}/` | 🔧 Pendiente | ❌ Vistas/URLs vacíos | ❌ |

### 3.8 Pagos

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `POST/GET /pagos/` | ✅ | ✅ | ✅ |
| `PATCH /pagos/{id}/actualizar_confirmacion/` | ✅ | ✅ | ✅ |
| `POST /pagos/{id}/rechazar/` | ✅ | ✅ | ✅ |
| `GET /pagos/{id}/pdf/a4/` | ✅ | ✅ | ✅ |
| `GET /pagos/{id}/pdf/80mm/` | ✅ | ✅ | ✅ |
| `GET /pagos/historial/` | ✅ | ✅ | ✅ |
| `POST /pagos/{id}/confirmar/` | ⚠️ Deprecated | ❌ No existe | ⚠️ |

### 3.9 Webhooks

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `GET /webhooks/` | 🔧 Pendiente | ❌ Vistas/URLs vacíos, serializers vacío | ❌ |

### 3.10 DGII

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `/api/v1/dgii/` | 🔧 Pendiente (interno) | ❌ Vistas/URLs vacíos (correcto, es interno) | ⚠️ |

### 3.11 Clientes

| Ruta | Doc | Real | Estado |
|:---|:---:|:---:|:---:|
| `POST/GET /clientes/` | ✅ | ✅ | ✅ |
| `GET/PATCH/DELETE /clientes/{rnc_cedula}/` | ✅ | ✅ | ✅ |

---

## 4. Modelos de Datos

### 4.1 Usuario (`users.Usuario`)

| Aspecto | Doc | Real |
|:---|:---|:---|
| Roles | `SUPERADMIN`, `ADMIN_EMPRESA` | `SUPERADMIN`, `ADMIN_EMPRESA`, **`USUARIO_EMPRESA`** (extra no documentado) |
| SuperAdmin sin empresa | ✅ | ✅ (`empresa_id` nullable) |
| Admin vinculado a empresa | ✅ | ✅ (`clean()` valida) |

### 4.2 Empresa (`empresas.Empresa`)

| Aspecto | Doc | Real |
|:---|:---|:---|
| Ambientes DGII | `testecf`, `ecf` | `testecf`, **`certecf`**, `ecf` (extra) |
| Certificado .p12 | Archivo en disco Ubuntu | `FileField` con `upload_to="certificados/"` |
| PIN cifrado con Fernet | ✅ | ✅ (`pin_cifrado` en `CertificadoDigital`) |
| Token DGII cifrado | No mencionado | ✅ (`TokenDGII.token_cifrado` con Fernet) |

### 4.3 Comprobante (`comprobantes.Comprobante`)

| Aspecto | Doc | Real |
|:---|:---|:---|
| **Estados** | `BORRADOR`, `EN_COLA`, `ACEPTADO`, `RECHAZADO`, `FALLO_CONEXION`, `ERROR_CERTIFICADO` | `BORRADOR`, `PENDIENTE`, `PROCESANDO`, `ACEPTADO`, `RECHAZADO`, `ANULADO`, `ERROR`, `CONTINGENCIA` |
| `EN_COLA` | Estado clave post-firma | ❌ No existe. Usa `PENDIENTE` |
| `PROCESANDO` | No existe en doc | ✅ Extra: estado intermedio durante envío DGII |
| `FALLO_CONEXION` | Error de red agotado | ❌ Reemplazado por `CONTINGENCIA` |
| `ERROR_CERTIFICADO` | Error de certificado expirado | ❌ Reemplazado por `ERROR` genérico |
| `ANULADO` | No listado | ✅ Existe en código |
| Inmutabilidad | Desde `EN_COLA` | ⚠️ Solo `ACEPTADO` y `ANULADO` son inmutables |
| `puede_anularse` | Solo `BORRADOR` | ✅ Solo `BORRADOR` |
| Transiciones validadas | No especificado | ❌ No hay `validate_transition()` |

### 4.4 Secuencial (`sequences.Secuencial`)

| Aspecto | Doc | Real |
|:---|:---|:---|
| Formato e-NCF | E + tipo(2) + secuencial(10 dígitos) = 13 chars | ✅ `_formatear_encf`: `f"E{self.tipo_ecf:02d}{numero:010d}"` |
| `select_for_update` | ✅ | ✅ (`sequences/services.py` línea 58) |
| Números viciados | Estado `VICIADO` | ❌ No existe estado `VICIADO`. El número se marca como consumido y no se reusa. |

### 4.5 API Key (`api_keys.ApiKey`)

| Scope (doc) | Scope (código) |
|:---|:---|
| `comprobantes:emision` | `comprobantes:crear` ❌ |
| `comprobantes:consultar` | `comprobantes:consultar` ✅ |
| `secuenciales:consultar` | `secuenciales:consultar` ✅ |
| `empresa:onboarding` | **❌ No existe en código** |
| *(no listado)* | `comprobantes:anular` (extra) |

### 4.6 Webhook

| Aspecto | Doc | Real |
|:---|:---|:---|
| URL del webhook | Campo en modelo `Empresa` | Modelo separado `Webhook` con FK a Empresa (diseño superior) |
| Secret hasheado (SHA-256) | ✅ | ✅ |
| HTTPS requerido | ✅ | ✅ (`clean()` valida) |
| `MAX_INTENTOS` | 3 | ❌ **5** (`MAX_INTENTOS = 5`) |

### 4.7 Auditoría (`audit.AuditLog`)

| Aspecto | Doc | Real |
|:---|:---|:---|
| Append-only Python | ✅ | ✅ (`save()` lanza si pk existe) |
| Firma HMAC-SHA256 | ✅ | ✅ (`signature`) |
| Trigger DB anti-UPDATE | ✅ (mencionado) | ✅ **SÍ existe** en migración `comprobantes/migrations/0002_immutability_triggers.py` (deps: audit.0001_initial) |
| Middleware de captura | Implícito | ❌ **Comentado en settings** (`core/settings/base.py` líneas 90-91) |
| Django Signals | Propuesto | ❌ No implementados |
| Firma incluye `id` y `creado_at` | No especificado | ❌ No incluidos en firma (líneas 153-161) |

---

## 5. Validaciones y Reglas de Negocio

### 5.1 Validación Matemática (ROUND_HALF_UP) 🔴 CRÍTICO

**Doc:** Validación línea por línea con `Decimal` + `ROUND_HALF_UP`.  
`MontoItem = ROUND_HALF_UP((Cantidad × PrecioUnitarioItem) - DescuentoMonto, 2)`  
Luego verifica que `MontoGravadoTotal + MontoExento + TotalITBIS == MontoTotal`.

**Real:**
- `apps/comprobantes/serializers.py` → **0 bytes (vacio)**
- `apps/comprobantes/services.py` → **0 bytes (vacio)**
- `apps/comprobantes/validators.py` → **No existe**
- El único check es `Comprobante.clean()` (líneas 304-310) que hace una suma agregada simple (`monto_gravado + monto_exento + monto_itbis == monto_total`), pero **no hay validación línea por línea ni ROUND_HALF_UP**.

➡️ **❌ NO IMPLEMENTADO**

### 5.2 Seguridad: PIN en Memoria Volátil

**Doc:** El PIN solo existe en RAM durante la firma. Nunca en logs, respuestas HTTP ni disco.

**Real:**
- ✅ `empresas/crypto.py`: `cifrar()`/`descifrar()` con Fernet
- ✅ `dgii/services.py` `_get_cert_pin()`: Descifra solo durante la firma
- ✅ `dgii/utils/xml_signer.py`: Recibe PIN como argumento en memoria
- ✅ PIN nunca se loggea ni aparece en respuestas HTTP

➡️ **✅ CORRECTO**

### 5.3 E33/E34 — Notas de Débito/Crédito

| Validación | Doc | Código (`Comprobante.clean()`) | Estado |
|:---|:---|:---|:---:|
| `ncf_modificado` existe y está `ACEPTADO` | ✅ | Líneas 285-292 | ✅ |
| `codigo_modificacion` obligatorio (1-5) | ✅ | Líneas 279-280 | ✅ |
| `razon_modificacion` max 90 chars | ✅ | Líneas 301-302 | ✅ |
| E34: `MontoTotal <= MontoTotal` original | ✅ | ❌ **No existe** | ❌ |
| RNC comprador coincide con original | No en doc | Líneas 294-299 (extra, correcto) | ➕ Extra |

➡️ **⚠️ PARCIAL — Falta validación de MontoTotal para E34**

### 5.4 E32 — Factura de Consumo (Umbral RD$250,000)

**Doc:** Si monto ≥ RD$250,000 → exige `rnc_comprador` o `cedula_comprador`.  
Si < RD$250,000 y vacío → fuerza "CONSUMIDOR FINAL".

**Código** (líneas 267-273):
```python
if self.tipo_ecf == 32:
    monto_total = self.monto_total or Decimal("0.00")
    if monto_total >= Decimal("250000.00"):
        if not self.rnc_comprador:
            errores["rnc_comprador"] = "...requiere RNC/Cédula..."
    if not self.rnc_comprador:
        self.razon_social_comprador = "CONSUMIDOR FINAL"
```

**Problemas:**
1. ❌ Solo valida `rnc_comprador`, ignora `cedula_comprador` (doc dice "o cedula_comprador")
2. ❌ Cuando monto ≥ 250K y no hay RNC: el código **tanto** asigna "CONSUMIDOR FINAL" **como** lanza error — comportamiento contradictorio
3. ❌ El `if not self.rnc_comprador` de línea 272 debería estar en `else` del bloque ≥250K

➡️ **⚠️ PARCIAL — Lógica incorrecta**

### 5.5 SaaS Guard (Onboarding) 🔴 CRÍTICO

**Doc** (líneas 227-232): Endpoint `POST /api/v1/secuencias/` que:
1. Extrae tipo e-CF de cada secuencia
2. Calcula volumen total
3. Consulta límite del plan en `suscripciones`
4. Si excede → `403 Forbidden`
5. Si cumple → registra rangos y guarda .p12

**Real:**
- ❌ No existe endpoint consolidado
- ❌ No hay validación de límite de plan contra rangos solicitados
- ❌ No hay carga de .p12 + PIN en un solo paso
- El doc mismo lo marca como "🔧 Pendiente"

➡️ **❌ NO IMPLEMENTADO**

### 5.6 Consumo de Balance (Paquete) 🔴 CRÍTICO

**Doc** (línea 177): "El comprobante se descuenta del Paquete en el paso síncrono, en el momento exacto en que el registro pasa a estado EN_COLA."

**Real:**
- `PaqueteComprobantes.consumir_comprobante()` existe (líneas 307-331) con `select_for_update`
- ✅ Tiene método `revertir_consumo()` para reversión
- ❌ **Pero `consumir_comprobante()` NO ES LLAMADO EN NINGÚN LADO** — no hay flujo que lo invoque

➡️ **❌ NO IMPLEMENTADO (método huérfano)**

---

## 6. Flujo Completo de Venta (La Carretera de Datos)

| Paso | Doc | Código | Estado |
|:---|:---|:---|:---:|
| 1. API-Key validación | Token, IP, scope | `ApiKeyAuthentication`: token ✅, IP ✅, scope ❌ | ⚠️ |
| 2. Suscripciones verifica balance | Suscripción ACTIVA + Paquete disponible | No hay código que llame a `consumir_comprobante()` | ❌ |
| 3. Serializer valida matemática | ROUND_HALF_UP línea por línea | Serializers vacío, solo `Comprobante.clean()` agregado | ❌ |
| 4. `select_for_update()` en secuencias | ✅ | ✅ (`obtener_proximo_encf`) | ✅ |
| 5. DGII firma XML | Construye XML, descifra PIN, firma | ✅ (`dgii/services.py`, `xml_builder.py`, `xml_signer.py`) | ✅ |
| 6. PostgreSQL guarda EN_COLA | Guarda + XML firmado | `dgii/services.py` guarda en estado PROCESANDO (no EN_COLA) | ⚠️ |
| 7. Responde 201 al POS | `uuid, e_ncf, server_timestamp, codigo_seguridad, sequence_status` | ❌ No hay vista que responda | ❌ |
| 8. Celery envía a DGII | Tarea asíncrona | ✅ (`reintentar_envio_ecf`) | ✅ |
| 9. Webhook notifica | POST asíncrono | ❌ Vistas/serializers vacíos | ❌ |

---

## 7. Seguridad y Ciberseguridad

| Regla | Doc | Real | Estado |
|:---|:---|:---|:---:|
| Inmutabilidad comprobantes | ✅ | ✅ (`save()` + trigger DB) | ✅ |
| PIN en memoria volátil | ✅ | ✅ | ✅ |
| e-NCF viciados | Estado `VICIADO` | ❌ No existe | ❌ |
| Backoff exponencial | [5min, 15min, 1h, 4h, 12h] | [30s, 2min, 10min, 1h, 4h] + sin jitter | ⚠️ |
| Append-only auditoría | Trigger DB + HMAC | HMAC ✅, Trigger DB ✅ (migración `0002_immutability_triggers`) | ⚠️ Middleware de captura sigue comentado |
| IP opcional API-Key | ✅ | ✅ (lista vacía = todas) | ✅ |
| Scopes mínimos por token | ✅ | ❌ Middleware no verifica scopes | ❌ |
| Idempotency Key | POS genera UUID único | Campo `unique=True` existe pero `default=uuid.uuid4` lo auto-genera, derrotando el propósito | ⚠️ |

---

## 8. Comparación Detallada de Estados de Comprobante

| Doc | Código | Diferencia |
|:---|:---|:---|
| `BORRADOR` | `BORRADOR` | ✅ |
| `EN_COLA` | `PENDIENTE` → `PROCESANDO` | ❌ Doc tiene 1 estado, código tiene 2 |
| `ACEPTADO` | `ACEPTADO` | ✅ |
| `RECHAZADO` | `RECHAZADO` | ✅ |
| `FALLO_CONEXION` | `CONTINGENCIA` | ❌ Nombre distinto, semántica distinta |
| `ERROR_CERTIFICADO` | `ERROR` | ❌ Fusionado en uno genérico |
| *(no listado)* | `ANULADO` | Extra en código |

---

## 9. Reintentos y Temporizadores

### 9.1 Reintentos Celery → DGII

| Intento | Doc | Código (`dgii/tasks.py`) |
|:---:|:---|:---|
| 1 | 5 min | 30 seg |
| 2 | 15 min | 2 min |
| 3 | 1 hora | 10 min |
| 4 | 4 horas | 1 hora |
| 5 | 12 horas | 4 horas |

**Jitter:** Doc dice "Backoff exponencial con jitter". Código usa valores fijos sin随机ización.

### 9.2 Reintentos Webhook → POS

**Doc:** Máximo 3 reintentos.  
**Código:** `MAX_INTENTOS = 5` en `webhooks/models.py`.

---

## 10. Otros Hallazgos

### 10.1 Middleware de API-Key no valida scopes

`ApiKeyAuthentication.authenticate()` solo verifica:
1. Token válido ✅
2. Empresa activa ✅
3. IP permitida ✅
4. **Scope contra endpoint ❌ — NO IMPLEMENTADO**

Una API Key con scope `secuenciales:consultar` podría llamar a cualquier endpoint sin restricción de scope.

### 10.2 TenantMiddleware usa header incorrecto

`audit/middleware.py` busca `Bearer` para identificar API Keys, pero `ApiKeyAuthentication` usa `Api-Key`. Por tanto, el TenantMiddleware nunca reconoce requests autenticados con API Key.

### 10.3 Webhook URL no está en Empresa

**Doc:** "La URL destino se registra como campo en el modelo `Empresa`".  
**Real:** Está en modelo separado `Webhook` con soporte multi-webhook por empresa. Mejor diseño, pero no coincide con el doc.

### 10.4 Celery Beat nocturno para FALLO_CONEXION no existe

**Doc** (línea 348): "Celery Beat nocturno reintenta automáticamente todos los `FALLO_CONEXION`".  
**Real:** No hay tal tarea en `core/celery.py`.

### 10.5 Prorrateo — lógica cuestionable

El cálculo en `_calcular_monto_prorrateado` usa `corte_anterior` y `primer_corte` de forma compleja que puede producir resultados inesperados vs la fórmula simple del doc.

### 10.6 ⚠️ `.env` local con credenciales reales (no commiteado)

El archivo `.env` contiene credenciales reales en disco local:
- `SECRET_KEY` = valor por defecto de `django-admin startproject`
- `DB_PASSWORD` = contraseña real de PostgreSQL
- `FERNET_KEY` = clave de cifrado real
- `SENTRY_DSN` = DSN real de Sentry
- `DGII_CERT_PASSWORD` = contraseña del certificado .p12

**Corrección:** El `.env` está en `.gitignore` (línea 2) y **nunca ha sido versionado en git** — no hay commits con él ni está en origin/main. El riesgo es de seguridad local (disco): cualquier persona con acceso al servidor puede leer las claves. Se recomienda rotar las credenciales y usar variables de entorno del sistema en producción.

### 10.7 ❌ `ClienteViewSet` no funciona con autenticación JWT

`apps/clientes/api/views.py`:
```python
def get_queryset(self):
    return Cliente.objects.filter(empresa=self.request.user)
```

Cuando la autenticación es JWT, `request.user` es una instancia de `Usuario`, no de `Empresa`. El FK `Cliente.empresa` apunta a `Empresa`, por lo que este filtro retorna vacío. Solo funciona con API Key (donde `request.user` es la `Empresa`).

El mismo problema afecta a `perform_create()` y `perform_update()`.

### 10.8 ⚠️ `pagos/permissions.py` usa `is_superuser` en vez de `rol`

Todo el sistema usa `user.rol` para permisos (consistente con `Usuario.ROL_SUPERADMIN`, etc.), pero `pagos/permissions.py` usa `request.user.is_superuser` que es el campo de Django `auth.User`, **no del modelo custom `Usuario`**.

```python
# apps/pagos/permissions.py línea 6
return request.user and request.user.is_authenticated and request.user.is_superuser
#                                           ^^^^^^^^^^^^^^ ❌ siempre False
```

Esto significa que **ningún superadmin puede acceder a pagos** porque `is_superuser` es `False` en el modelo custom (a menos que se setee explícitamente, y en `create_superuser` de `UsuarioManager` se setea, pero el permiso debería checkear `rol`).

### 10.9 ⚠️ `RecoverPasswordView` devuelve `temp_password` en la respuesta HTTP

`apps/users/views.py` líneas 107-111:
```python
return Response({
    "mensaje": "Recuperación simulada...",
    "email": email,
    "temp_password": temp_password,  # ← contraseña en texto plano en HTTP response
})
```

Aunque está comentado como "solo para desarrollo", es un riesgo de seguridad si se despliega accidentalmente. La contraseña temporal nunca debe viajar por la red.

### 10.10 ⚠️ Inconsistencia: `ValueError` vs `ValidationError` en inmutabilidad

`DGIILog.save()` y `AuditLog.save()` lanzan `ValueError` cuando se intenta modificar un registro existente:
```python
raise ValueError("Los registros de auditoría no pueden modificarse.")
raise ValueError("Los logs DGII no pueden eliminarse.")
```

`Comprobante.save()` y `Comprobante.delete()` lanzan `ValidationError` (de Django):
```python
raise ValidationError("No se puede modificar un comprobante en estado...")
raise ValidationError("Los comprobantes no pueden eliminarse.")
```

`ValidationError` es capturado por DRF y convertido en respuesta 400. `ValueError` causa un 500. **Deben ser consistentes.**

### 10.11 ⚠️ `CleanModelSerializer` puede fallar con `partial=True` (PATCH)

`core/serializers.py` en `validate()`:
```python
instance = ModelClass(**attrs)  # ← falla si faltan campos required
```

Cuando se hace un PATCH parcial, `attrs` solo contiene los campos enviados. Si el modelo tiene campos `required=True` sin default, `ModelClass(**attrs)` lanza `TypeError`. El `CleanModelSerializer` no maneja este caso.

### 10.12 ⚠️ `notificar_pagos_proximos` es un stub

`apps/pagos/tasks.py` línea 169-172:
```python
@shared_task(name='pagos.notificar_pagos_proximos')
def notificar_pagos_proximos():
    logger.info("[PAGOS] Iniciando notificacion de pagos proximos")
    pass  # ← sin implementación
```

La tarea está registrada en `CELERY_BEAT_SCHEDULE` y se ejecuta diario a las 08:00, pero no hace nada.

### 10.13 ⚠️ Tests vacíos en varias apps

| App | tests.py | Estado |
|:---|:---|:---:|
| `subscriptions/tests.py` | Solo `TestCase` import | ❌ Vacío |
| `sequences/tests.py` | Solo `TestCase` import | ❌ Vacío |
| `webhooks/tests.py` | Solo `TestCase` import | ❌ Vacío |
| `pagos/tests/` | `test_tasks.py` con 273 líneas | ✅ Tiene tests |
| `users/tests.py` | 54 líneas | ⚠️ Solo test de API Key auth |
| `empresas/tests.py` | 102 líneas | ✅ Tests de certificado |
| `comprobantes/tests.py` | 223 líneas | ✅ Tests de validación |
| `clientes/tests.py` | 180 líneas | ✅ Tests de modelo y API |

---

## 11. Resumen de Severidad

### ✅ Correcto (7)
1. PIN en memoria volátil
2. `select_for_update` en secuencias
3. IP opcional en API-Key
4. Inmutabilidad de comprobantes (Python + trigger DB)
5. Cifrado Fernet funcional
6. Idempotency field (existe como columna)
7. Trigger DB anti-UPDATE existe para audit, comprobantes, detalles y DGII logs

### ⚠️ Parcial / Con diferencias (15)
1. Estados de comprobante (5 estados diferentes al doc)
2. E33/E34 (falta validación MontoTotal)
3. E32 umbral (no valida cédula, lógica contradictoria)
4. Backoff Celery (valores distintos, sin jitter)
5. Append-only auditoría (trigger DB ✅, middleware de captura ❌)
6. Prorrateo (lógica cuestionable)
7. Ruta XML (path distinto, sin FileSystemStorage)
8. Webhook URL (en modelo separado, no en Empresa)
9. `RecoverPasswordView` devuelve temp_password en response
10. `ValueError` vs `ValidationError` inconsistente en modelos append-only
11. `CleanModelSerializer` falla con partial updates
12. `pagos/permissions.py` usa `is_superuser` en vez de `rol`
13. `notificar_pagos_proximos` es stub
14. Tests vacíos en 3 apps
15. `.env` local con credenciales reales — en `.gitignore`, no commiteado

### ❌ No implementado / Crítico (11)
1. **Validación matemática ROUND_HALF_UP** — Serializers vacío
2. **SaaS Guard** — No existe endpoint de onboarding
3. **Consumo de balance** — `consumir_comprobante()` huérfano
4. **Scopes validation** — Middleware no verifica scopes
5. **Comprobantes CRUD** — Toda la app es un shell vacío
6. **Webhooks funcionales** — Vistas/serializers vacíos
7. **App `notificaciones`** — No existe
8. **Middleware de auditoría** — Comentado en settings
9. **e-NCF viciados** — Estado `VICIADO` no existe
10. **Endpoint `POST /api/v1/secuencias/`** — No registrado
11. **`ClienteViewSet` no funciona con JWT** — Solo funciona con API Key

---

## 12. Conclusión

El proyecto tiene una **base sólida de modelos y servicios DGII**, pero la **lógica de negocio central (comprobantes)** y varios **mecanismos de seguridad (scopes, validación matemática, consumo de balance)** están pendientes de implementar. 

La app `comprobantes` —el núcleo transaccional del sistema— es un cascarón vacío: serializers (0 bytes), services (0 bytes), vistas stub, URLs vacías. Sin ella, el pipeline completo de emisión de e-CF descrito en la arquitectura no puede funcionar.

**Hallazgos adicionales críticos:**
1. El `ClienteViewSet` solo funciona con API Key, no con JWT — bug funcional
2. Los permisos de pagos usan `is_superuser` en vez de `rol` — bloquea acceso
3. Hay 3 apps sin tests (subscriptions, sequences, webhooks)
4. La tarea Celery `notificar_pagos_proximos` no hace nada
5. `.env` local con credenciales reales — rotación recomendada
