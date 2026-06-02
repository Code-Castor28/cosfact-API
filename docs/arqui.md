# Documento de Arquitectura Final: DerejFactAPI
## Middleware Multi-tenant de Facturación Electrónica — DGII, República Dominicana

---

## 1. Objetivo General del Proyecto

DerejFactAPI es una **API puente (middleware) de facturación electrónica pura**, asíncrona, segura y multi-tenant, diseñada específicamente para el contexto fiscal de la República Dominicana. Actúa estrictamente como un motor de validación matemática, numeración atómica de e-NCF, firma criptográfica síncrona (PKCS#12) y pasarela de comunicación asíncrona con la DGII.

### Línea Roja de Arquitectura — Lo que NO es este proyecto

| ❌ No es | Razón |
|:---|:---|
| Un ERP o POS | No gestiona inventarios, cuentas por cobrar ni turnos de cajeros |
| Un CRM | Los datos del comprador viajan efímeros y planos en el payload. El directorio de clientes es solo indexación fiscal opcional para evitar redigitación en caja |
| Un sistema de analítica | La base de datos existe para auditoría, resiliencia fiscal y custodia del XML/JSON, no para reportes de ventas |
| Un procesador de pagos | Los pagos al SaaS se registran manualmente por el SuperAdmin; no hay pasarela de cobro automático |

---

## 2. Stack Tecnológico

| Componente | Tecnología |
|:---|:---|
| Framework | Django + Django REST Framework |
| Base de datos | PostgreSQL |
| Cola de tareas | Celery + Redis (broker) |
| Criptografía | `cryptography` (Fernet para PIN, PKCS#12 para firma XML) |
| Almacenamiento XML | `FileSystemStorage` en disco local Ubuntu (`/var/www/derejfact/media/xmls/`) |
| Autenticación humana | JWT (`djangorestframework-simplejwt`) |
| Autenticación POS | API Key personalizada (`ApiKeyAuthentication`) |
| Comunicación DGII | SOAP/XML sobre HTTPS |

---

## 3. Mapa del Ecosistema de Aplicaciones

```
[PANEL WEB — CONTROL HUMANO]
  usuarios ──(JWT)──> empresas ──> auditoria (Append-Only)
                         │
                         ▼
                       pagos ──(e-CF DerejSoft)──> dgii (Firma/Envío)
                         │
                (Desbloquea balance)
                         │
                         ▼
[POS — API KEY]    suscripciones (Control de Créditos)
                         │
                         ▼
  api-keys ──(Scopes)──> secuencias (Certificado + Rangos)
     │                        │
     │                        ▼
     └──────────────> comprobantes ──(Firma Síncrona)──> dgii (SOAP)
                          │                                    │
                          ▼                                    ▼
                       webhooks <──────(Notifica Estado Final)─┘
                          │
                   notificaciones (Correos a Humanos)
```

---

## 4. Diccionario de Responsabilidades por App

### 4.1 App: `usuarios`

**Responsabilidad:** Gestionar credenciales, roles y sesiones de los seres humanos que acceden al panel administrativo web de DerejSoft.

**Roles disponibles:**

| Rol | Permisos |
|:---|:---|
| `SUPERADMIN` | Acceso total. No tiene empresa asignada. Registra pagos manualmente. |
| `ADMIN_EMPRESA` | Acceso al panel de su empresa. Visualiza comprobantes, historial y suscripción. |

**Comunicación inter-app:**
- Se enlaza mediante `ForeignKey` a `empresas` para que el administrador vea el historial fiscal y de pagos de su negocio.
- Proporciona el actor (`user_id`) que registra la app `auditoria` en cada acción crítica.

**Endpoints activos:**

| Método | Ruta | Acceso |
|:---:|:---|:---:|
| `POST` | `/api/v1/auth/login/` | Público |
| `POST` | `/api/v1/auth/token/refresh/` | Público |
| `POST` | `/api/v1/auth/recover-password/` | Público |
| `POST` | `/api/v1/usuarios/` | JWT |
| `GET` | `/api/v1/usuarios/` | JWT |
| `GET/PATCH` | `/api/v1/usuarios/me/` | JWT |
| `POST` | `/api/v1/usuarios/me/change-password/` | JWT |

---

### 4.2 App: `empresas`

**Responsabilidad:** Núcleo y pivote del aislamiento multi-tenant. Almacena la identidad fiscal maestra de cada negocio cliente y custodia sus credenciales criptográficas.

**Modelos clave:**

- `Empresa`: RNC, Razón Social, Nombre Comercial, Ambiente DGII (`testecf` / `ecf`), Estado, Activa.
- `CertificadoDigital`: Archivo `.p12` (disco Ubuntu), PIN cifrado con Fernet, fecha de vencimiento.

**Regla de seguridad del PIN:**
> El PIN nunca se persiste en texto plano. Se cifra simétricamente con `CRYPTOGRAPHY_MASTER_KEY` usando `cryptography.fernet` antes de guardarse en PostgreSQL. Se descifra **únicamente** en la memoria volátil del proceso de Python durante los milisegundos que dura la firma criptográfica, destruyéndose inmediatamente después.

**Comunicación inter-app:**
- Todas las apps transaccionales filtran sus queries con `empresa_id` para garantizar el aislamiento.
- La app `secuencias` escribe el `.p12` y el PIN cifrado aquí durante el onboarding.
- La app `dgii` lee el certificado desde aquí durante la firma síncrona.
- La app `notificaciones` recibe alertas de esta app cuando el `.p12` vence en 15 días.

**Endpoints activos:**

| Método | Ruta | Acceso |
|:---:|:---|:---:|
| `POST` | `/api/v1/empresas/` | JWT |
| `GET` | `/api/v1/empresas/` | JWT / API-Key |
| `GET` | `/api/v1/empresas/{id}/` | JWT / API-Key |
| `GET` | `/api/v1/empresas/{id}/suscripcion/` | JWT |
| `GET` | `/api/v1/empresas/{id}/comprobantes/` | JWT |

---

### 4.3 App: `api-keys`

**Responsabilidad:** Seguridad periférica y autenticación del tráfico entrante desde las cajas registradoras externas mediante tokens con scopes estrictos.

**Formato del token:**
```
<rnc_sin_guiones>_<token_aleatorio>
Ejemplo: 131793916_x8f9k3abcdef...
```

**Scopes disponibles (los únicos abiertos a API-Key):**

| Scope | Endpoint habilitado | Uso |
|:---|:---|:---|
| `comprobantes:emision` | `POST /api/v1/comprobantes/` | Facturación diaria desde la caja |
| `comprobantes:consultar` | `GET /api/v1/comprobantes/` y `/{id}/` | Consulta de historial fiscal |
| `secuenciales:consultar` | `GET /api/v1/secuenciales/` | Verificación de disponibilidad |
| `empresa:onboarding` | `POST /api/v1/secuencias/` | Carga inicial de `.p12`, PIN y rangos |

> **Regla absoluta:** Ninguna API-Key, bajo ningún scope, puede interactuar con `pagos`, `usuarios` ni `auditoria`.

**Validaciones del middleware `ApiKeyAuthentication`:**
1. Extrae el prefijo RNC del token para identificar la empresa en PostgreSQL.
2. Verifica que la key no esté revocada ni expirada.
3. Valida que la IP del request esté en `allowed_ips` (campo opcional; si está vacío, se omite la restricción para compatibilidad con IPs dinámicas de proveedores dominicanos como Claro, Altice y Wind).
4. Verifica que el scope del token cubra el endpoint solicitado.
5. Inyecta la `Empresa` en `request.user` para el aislamiento multi-tenant.

**Endpoints activos:**

| Método | Ruta | Acceso |
|:---:|:---|:---:|
| `POST` | `/api/v1/api-keys/` | JWT |
| `GET` | `/api/v1/api-keys/` | JWT |
| `POST` | `/api/v1/api-keys/{id}/revocar/` | JWT |
| `POST` | `/api/v1/api-keys/{id}/rotar/` | JWT |

---

### 4.4 App: `suscripciones`

**Responsabilidad:** Cortafuegos de monetización del SaaS. Controla los límites operativos de cada empresa cliente mediante tres sub-módulos inseparables.

**Sub-módulos:**

| Sub-módulo | Modelo | Función |
|:---|:---|:---|
| Planes | `Plan` | Catálogo comercial: precio, límite de comprobantes, tipos de e-CF permitidos |
| Suscripciones | `Suscripcion` | Estado del contrato temporal del cliente (ACTIVA, VENCIDA, SUSPENDIDA) |
| Paquetes | `Paquete` | Contador atómico de comprobantes disponibles (de suscripción mensual o adicionales) |

**Regla de consumo de balance:**
> El comprobante se descuenta del `Paquete` en el paso **síncrono**, en el momento exacto en que el registro pasa a estado `EN_COLA`. Esto garantiza que ráfagas de peticiones concurrentes desde la caja no puedan sobrepasar el límite contratado antes de que Celery actualice el balance.

**Comunicación inter-app:**
- `comprobantes` la consulta antes de asignar el e-NCF.
- `secuencias` la consulta para validar que el rango solicitado entre dentro del plan.
- `pagos` la actualiza al confirmar un cobro, activando el nuevo balance.
- `notificaciones` la monitoriza para alertar cuando el balance cae bajo el 10%.

**Endpoints activos:**

| Método | Ruta | Acceso |
|:---:|:---|:---:|
| `POST` | `/api/v1/planes/` | JWT |
| `GET` | `/api/v1/planes/` | JWT |
| `POST` | `/api/v1/suscripciones/` | JWT |
| `GET` | `/api/v1/suscripciones/` | JWT |
| `POST` | `/api/v1/paquetes/` | JWT |
| `GET` | `/api/v1/paquetes/` | JWT |

---

### 4.5 App: `secuencias`

**Responsabilidad:** Portal único de configuración inicial y renovación de rangos de e-NCF autorizados por la DGII. Unifica en un solo endpoint la carga del certificado digital y el registro de secuencias fiscales.

**Estructura del e-NCF dominicano (13 caracteres):**
```
E  3  1  0000000001
│  │  │  └─ 10 dígitos secuenciales
│  └──┘
│   Tipo de e-CF (2 dígitos: 31, 32, 34, etc.)
└─ Serie fija "E"

Ejemplo rango: E310000000001 → E310000000020 (20 comprobantes Tipo 31)
```

**Payload del POS (POST único consolidado):**
```json
{
  "actualizar_certificado": true,
  "archivo_p12": "<base64>",
  "pin_texto_plano": "mi_pin_secreto",
  "secuencias": [
    { "desde": "E310000000001", "hasta": "E310000000020" },
    { "desde": "E320000000001", "hasta": "E320000000020" }
  ]
}
```
> Si `actualizar_certificado: false`, se ignoran `archivo_p12` y `pin_texto_plano`, preservando el certificado existente. Útil para renovaciones mensuales de rango sin tocar el certificado anual.

**Lógica del SaaS Guard:**
1. Para cada nodo en `secuencias`, extrae el tipo de e-CF (posiciones 2-3 del string) y calcula el volumen: `hasta[3:] - desde[3:] + 1`.
2. Suma el volumen total de todos los tipos en el payload.
3. Consulta a `suscripciones` el límite disponible en el plan activo.
4. Si el volumen total **supera** el límite: retorna `403 Forbidden` — bloquea todo el payload.
5. Si **cumple**: registra los rangos en la tabla `Secuencial` y guarda el `.p12` y PIN cifrado en `empresas`.

**Regla de bloqueo por agotamiento:**
> Cuando el puntero de `comprobantes` alcanza el `hasta` de un tipo, ese tipo queda bloqueado. El endpoint `POST /api/v1/secuencias/` permanece **bloqueado para esa empresa** hasta que el SuperAdmin confirme un nuevo pago en `pagos`, lo que desbloquea temporalmente el endpoint para que el POS cargue el nuevo rango.

**Vencimiento anual:**
> Los rangos de e-NCF otorgados por la DGII vencen el 31 de diciembre del año siguiente a su autorización. La app `notificaciones` alerta al administrador con anticipación.

**Endpoints:**

| Método | Ruta | Acceso |
|:---:|:---|:---:|
| `POST` | `/api/v1/secuencias/` | API-Key (`empresa:onboarding`) |
| `GET` | `/api/v1/secuenciales/` | JWT |
| `GET` | `/api/v1/secuenciales/{id}/preview/` | JWT |
| `POST` | `/api/v1/secuenciales/{id}/bloquear/` | JWT |
| `POST` | `/api/v1/secuenciales/{id}/desbloquear/` | JWT |

---

### 4.6 App: `comprobantes`

**Responsabilidad:** Motor transaccional de venta diaria. Valida, firma síncronamente y persiste cada documento fiscal. Gobierna la máquina de estados inmutable del e-CF.

**Tipos de e-CF soportados en Fase 1:**

| Código | Tipo | Validación especial |
|:---:|:---|:---|
| 31 | Factura de Crédito Fiscal | `rnc_comprador` y `razon_social_comprador` obligatorios |
| 32 | Factura de Consumo | Si monto ≥ RD$250,000 → exige `rnc_comprador` o `cedula_comprador`. Si < RD$250,000 y vacío → fuerza "CONSUMIDOR FINAL" |
| 33 | Nota de Débito | Exige `ncf_modificado` en estado `ACEPTADO` en DB + `codigo_modificacion` (1-5) + `razon_modificacion` (max 90 chars) |
| 34 | Nota de Crédito | Igual que Tipo 33. Valida que `MontoTotal` ≤ `MontoTotal` del e-CF original |
| 41 | Comprobante de Compras | — |

**Flujo síncrono (<250ms):**

```
1. [api-keys]       → Valida token y scope
2. [suscripciones]  → Verifica balance > 0 en Paquete activo
3. [comprobantes]   → Valida matemática línea por línea (Decimal, ROUND_HALF_UP)
                      → select_for_update() sobre rango en [secuencias]
                      → Asigna e-NCF e incrementa puntero
4. [dgii (local)]   → Construye XML estructural
                      → Descifra PIN en memoria volátil
                      → Firma con .p12 de [empresas]
                      → Extrae primeros 6 chars del SignatureValue → codigo_seguridad
5. [PostgreSQL]     → Guarda registro en estado EN_COLA + XML firmado
```

**Respuesta síncrona al POS:**
```json
{
  "uuid": "<transaccion_uuid>",
  "e_ncf": "E310000000001",
  "server_timestamp": "2026-06-01T21:00:00Z",
  "codigo_seguridad": "A4F9E2",
  "sequence_status": "consumed"
}
```
> El `server_timestamp` es siempre del servidor, nunca del POS. La hora impresa en el ticket fiscal debe coincidir con el log interno de la API para auditorías de la DGII.

**Regla de inmutabilidad:**
> Una vez que un comprobante pasa a `EN_COLA`, sus montos, e-NCF y estructura XML son **estrictamente inmutables**. No existen endpoints `PUT` o `PATCH` para documentos procesados. Solo existe `PATCH` para documentos en estado `BORRADOR`.

**Motor matemático (Serializer):**

```
Por cada ítem:
  MontoItem = ROUND_HALF_UP((Cantidad × PrecioUnitarioItem) - DescuentoMonto, 2)

Totales de control:
  MontoGravadoTotal = Σ(MontoItem donde IndicadorFacturacion ∈ {1,2,3})
  TotalITBIS        = Σ(ITBIS calculado por tasa según indicador)
  MontoTotal        = MontoGravadoTotal + MontoExento + TotalITBIS + ImpuestosAdicionales

Si MontoTotal_calculado ≠ MontoTotal_enviado → HTTP 400 (frena antes de consumir e-NCF)
```

**Endpoints activos (Fase 1 — pendientes de implementar):**

| Método | Ruta | Acceso |
|:---:|:---|:---:|
| `POST` | `/api/v1/comprobantes/` | API-Key (`comprobantes:emision`) |
| `GET` | `/api/v1/comprobantes/` | API-Key (`comprobantes:consultar`) / JWT |
| `GET` | `/api/v1/comprobantes/{id}/` | API-Key (`comprobantes:consultar`) / JWT |
| `PATCH` | `/api/v1/comprobantes/{id}/` | API-Key — solo si estado es `BORRADOR` |

---

### 4.7 App: `dgii`

**Responsabilidad:** Pasarela criptográfica y de comunicación externa de bajo nivel. No expone vistas públicas al POS. Opera en dos fases: firma local (síncrona) y transmisión a Impuestos Internos (asíncrona).

**Fase Síncrona (invocada desde la vista de `comprobantes`):**
1. Recibe el JSON validado y construye el XML estructural conforme al esquema XSD de la DGII (versión 1.0).
2. Descifra el PIN en memoria usando Fernet.
3. Firma el XML usando la clave privada del `.p12` con el estándar `XMLDSig`.
4. Devuelve el string del XML firmado y el `codigo_seguridad` (6 primeros chars del `SignatureValue`).

**Fase Asíncrona (Worker Celery — invocada tras responder al POS):**
1. Toma el UUID del comprobante y lee el XML firmado de PostgreSQL.
2. Transmite via SOAP/HTTPS al Web Service de la DGII (`testecf.dgii.gov.do` o `ecf.dgii.gov.do` según ambiente).
3. Recibe el `TrackId` de seguimiento.
4. Actualiza el estado del comprobante en `comprobantes` a `ACEPTADO` o `RECHAZADO`.
5. Invoca a `webhooks` para notificar al POS.

**Estrategia de reintentos (Escenario B — caída de red):**

| Reintento | Espera aproximada |
|:---:|:---|
| 1 | 5 minutos |
| 2 | 15 minutos |
| 3 | 1 hora |
| 4 | 4 horas |
| 5 | 12 horas |

> Tras 5 reintentos fallidos → estado `FALLO_CONEXION`. Celery Beat nocturno reintenta automáticamente todos los `FALLO_CONEXION` cuando detecta que el servidor de la DGII ha revivido.

**Nota sobre e-NCF rechazados:**
> Si el estado final es `RECHAZADO`, ese número de e-NCF queda marcado como **viciado/inutilizable** en la tabla `Secuencial`. El POS debe emitir una nueva petición con el siguiente número correlativo disponible.

---

### 4.8 App: `webhooks`

**Responsabilidad:** Canal crítico de integración máquina a máquina (API → POS). Garantiza que el servidor del comercio se entere del veredicto fiscal final de forma asíncrona, sin polling.

**Formato del payload enviado al POS:**
```json
{
  "event": "comprobante.aceptado",
  "uuid": "<transaccion_uuid>",
  "e_ncf": "E310000000001",
  "estado": "ACEPTADO",
  "track_id": "<dgii_track_id>",
  "timestamp": "2026-06-01T21:05:00Z"
}
```

**Eventos posibles:**

| Event | Estado origen |
|:---|:---|
| `comprobante.aceptado` | `ACEPTADO` |
| `comprobante.rechazado` | `RECHAZADO` + motivo DGII |
| `comprobante.fallo_conexion` | `FALLO_CONEXION` |
| `comprobante.error_certificado` | `ERROR_CERTIFICADO` |

**Estrategia de entrega con tolerancia a fallos:**
- Máximo 3 reintentos si el POS no responde con `HTTP 200 OK`.
- Cada fallo queda registrado en la tabla de logs de `webhooks` con la IP, timestamp y código de error HTTP para soporte técnico.

**Configuración de la URL del Webhook:**
> La URL destino se registra como campo en el modelo `Empresa`. Permite configurar una URL diferente por empresa desde el panel administrativo (JWT).

**Endpoints activos:**

| Método | Ruta | Acceso |
|:---:|:---|:---:|
| `GET` | `/api/v1/webhooks/` | JWT — historial de entregas |

---

### 4.9 App: `pagos`

**Responsabilidad:** Control de caja del SaaS de DerejSoft. Registra ingresos, emite comprobantes fiscales propios usando el motor nativo de la API, desbloquea cuotas y genera recibos en PDF.

**Orígenes del pago:**

| Origen | Creación | Efecto al confirmar |
|:---|:---|:---|
| `RENOVACION` | Manual (SuperAdmin) o automático (Celery Beat 15 días antes del vencimiento) | Actualiza fechas de suscripción + crea Paquete |
| `ADICIONAL` | Solo manual (SuperAdmin) | Crea Paquete extra sin tocar fechas |

**Flujo al confirmar un pago:**
1. Cambia estado del pago a `CONFIRMADO`.
2. Actualiza la `Suscripcion` de la empresa (estado `ACTIVA`, nueva `fecha_renovacion`).
3. Crea o recarga el `Paquete` de comprobantes en `suscripciones`.
4. Desbloquea el endpoint `POST /api/v1/secuencias/` para que el POS cargue nuevos rangos.
5. Genera el e-CF de DerejSoft usando sus propias secuencias y el motor de `dgii`.
6. Invoca a `notificaciones` para enviar el recibo PDF al cliente por correo.

**Prorrateo automático (primer pago):**
```
Mensual: precio_mensual × (días_usados / días_del_período)
Anual:   precio_anual   × (días_usados / 365)
```

**Generación automática (Celery Beat — diario 00:00):**
- Busca suscripciones que vencen en los próximos 15 días.
- Crea `Pago(estado=PENDIENTE, tipo=RENOVACION)` si no existe uno pendiente ya.
- No genera `HistorialPago` hasta que el SuperAdmin confirme.

**Endpoints activos:**

| Método | Ruta | Acceso |
|:---:|:---|:---:|
| `POST` | `/api/v1/pagos/` | JWT |
| `GET` | `/api/v1/pagos/` | JWT |
| `PATCH` | `/api/v1/pagos/{id}/actualizar_confirmacion/` | JWT |
| `POST` | `/api/v1/pagos/{id}/rechazar/` | JWT |
| `GET` | `/api/v1/pagos/{id}/pdf/a4/` | JWT |
| `GET` | `/api/v1/pagos/{id}/pdf/80mm/` | JWT |
| `GET` | `/api/v1/pagos/historial/` | JWT |

---

### 4.10 App: `notificaciones`

**Responsabilidad:** Canal de comunicación de sistema a humano. Envía correos electrónicos HTML vía SMTP con información relevante para el administrador del negocio o el cliente de DerejSoft.

**Eventos que disparan notificaciones:**

| Disparador | App origen | Contenido del correo |
|:---|:---|:---|
| Pago confirmado | `pagos` | Recibo PDF del e-CF de DerejSoft como adjunto |
| Balance bajo (<10%) | `suscripciones` (Celery Beat diario) | Alerta de comprobantes por agotarse |
| Certificado por vencer | `empresas` (Celery Beat diario) | Aviso 15 días antes del vencimiento del `.p12` |
| Suscripción próxima a vencer | `suscripciones` (Celery Beat diario) | Aviso de renovación pendiente |
| Suscripción suspendida | `suscripciones` | Notificación de bloqueo por falta de pago |

> Esta app **no notifica por cada factura emitida**. Solo actúa ante eventos administrativos o de ciclo de vida del servicio.

---

### 4.11 App: `auditoria`

**Responsabilidad:** Caja negra del servidor Ubuntu. Registro inmutable y silencioso de todas las acciones críticas para auditoría forense y cumplimiento de ciberseguridad.

**Eventos capturados (pasivamente vía Django Signals):**

| Evento | App monitoreada |
|:---|:---|
| Creación/rotación/revocación de API Key | `api-keys` |
| Actualización de `.p12` o PIN | `empresas` |
| Modificación manual de rangos secuenciales | `secuencias` |
| Confirmación o rechazo de pagos | `pagos` |
| Cambio de rol de usuario | `usuarios` |

**Estructura del registro (Append-Only — sin UPDATE ni DELETE):**

```json
{
  "timestamp": "2026-06-01T21:00:00Z",
  "actor_id": "<user_uuid_o_apikey_prefix>",
  "actor_tipo": "SUPERADMIN | ADMIN_EMPRESA | API_KEY",
  "ip_origen": "190.0.2.10",
  "app": "api-keys",
  "accion": "REVOCACION",
  "estado_anterior": { ... },
  "estado_posterior": { ... }
}
```

---

## 5. Tabla Maestra de Estados del Comprobante

| Estado | Origen | Descripción | Acción del Sistema |
|:---|:---|:---|:---|
| `BORRADOR` | API Síncrono | Registro validado matemáticamente pero aún no encolado. | Único estado donde `puede_anularse = True`. Permite `PATCH`. |
| `EN_COLA` | API Síncrono | e-NCF asignado, XML firmado. Respuesta HTTP 201 enviada al POS. | Registro inmutable. Se transfiere a Celery para envío a DGII. |
| `ACEPTADO` | Celery Asíncrono | La DGII validó y aceptó el XML firmado. | Se guarda XML definitivo con sello digital. Se dispara Webhook de éxito. |
| `RECHAZADO` | Celery Asíncrono | La DGII rechazó el XML por inconsistencia fiscal. | e-NCF marcado como viciado. Se dispara Webhook crítico inmediato al POS. |
| `FALLO_CONEXION` | Celery Asíncrono | Agotados los 5 reintentos por caída de red de la DGII. | Se activa bandera de contingencia en `/api/v1/pos/ready/`. Celery Beat lo reintenta nocturnamente. |
| `ERROR_CERTIFICADO` | Celery Asíncrono | El worker detectó que el `.p12` expiró al momento de firmar. | Aborta la tarea. Registra en `auditoria`. Bloquea emisión global en `/api/v1/pos/ready/`. Alerta a `notificaciones`. |

---

## 6. Flujo Lógico Completo de una Venta (La Carretera de Datos)

```
[POS]
  │  HTTP POST /api/v1/comprobantes/
  │  Header: Authorization: Api-Key 131793916_xxxxx
  ▼
[api-keys]
  → Valida token, IP y scope (comprobantes:emision)
  → Inyecta Empresa en request.user
  ▼
[suscripciones]
  → Verifica Suscripcion.estado == ACTIVA
  → Verifica Paquete.comprobantes_usados < total_comprobantes
  ▼
[comprobantes — Serializer]
  → Valida matemática artículo por artículo (Decimal ROUND_HALF_UP)
  → Fórmula: MontoItem = (Cantidad × Precio) - Descuento
  → Verifica que sumatoria == monto_total enviado por POS
  ▼
[secuencias — select_for_update()]
  → Verifica que el tipo de e-CF no esté bloqueado por agotamiento
  → Asigna siguiente e-NCF disponible
  → Incrementa puntero en +1
  ▼
[dgii — Fase Síncrona]
  → Construye XML estructural (conforme a XSD DGII v1.0)
  → Descifra PIN (Fernet) en memoria volátil
  → Firma XML con clave privada del .p12
  → Extrae codigo_seguridad (6 primeros chars de SignatureValue)
  ▼
[PostgreSQL]
  → Guarda Comprobante en estado EN_COLA
  → Persiste XML firmado en disco Ubuntu
  ▼
──────────────────────────────────────────────────────────
  RESPUESTA SÍNCRONA AL POS — HTTP 201 Created (<250ms)
  {
    "uuid": "...",
    "e_ncf": "E310000000001",
    "server_timestamp": "2026-06-01T21:00:00Z",
    "codigo_seguridad": "A4F9E2",
    "sequence_status": "consumed"
  }
──────────────────────────────────────────────────────────
  ▼ (Disparo asíncrono a Celery Worker)
[dgii — Worker Celery]
  → Lee XML firmado de PostgreSQL por UUID
  → Transmite via SOAP/HTTPS a ecf.dgii.gov.do
  → Recibe TrackId
  → Actualiza estado: ACEPTADO | RECHAZADO | FALLO_CONEXION
  ▼
[webhooks]
  → Construye payload JSON
  → HTTP POST asíncrono con reintentos (máx 3) a URL del cliente
  → Registra log de entrega
```

---

## 7. Flujo del Ciclo de Vida del Cliente (Onboarding y Renovación)

```
[SuperAdmin crea Empresa + Suscripción + Plan]
  ↓
[SuperAdmin crea API Key con scope empresa:onboarding]
  ↓
[POS hace POST /api/v1/secuencias/ con .p12, PIN y rangos DGII]
  ↓ (SaaS Guard)
[API valida: Σ comprobantes solicitados ≤ límite del plan]
  ↓ (Aprobado)
[Empresa queda ACTIVA — POS puede facturar]
  ↓
[POS usa POST /api/v1/comprobantes/ diariamente]
  ↓ (Agotamiento)
[Tipo bloqueado → POS recibe error "Secuencia agotada"]
  ↓
[Cliente contacta SuperAdmin → SuperAdmin crea Pago en panel]
  ↓
[SuperAdmin confirma pago → pagos actualiza Suscripción y Paquete]
  ↓
[Endpoint /secuencias/ desbloqueado temporalmente]
  ↓
[POS envía nuevo rango DGII → ciclo se reinicia]
```

---

## 8. Reglas de Control de Riesgos y Ciberseguridad

1. **Inmutabilidad absoluta:** Una vez en `EN_COLA`, montos, e-NCF y XML son inmutables sin excepción.
2. **PIN en memoria volátil:** El PIN solo existe en RAM durante la firma. Nunca en logs, respuestas HTTP ni disco en texto plano.
3. **e-NCF viciados por rechazo:** Los números rechazados por la DGII no se reutilizan. Quedan marcados como `VICIADO` en la tabla `Secuencial`. La pérdida del número es obligatoria por normativa.
4. **Backoff exponencial con jitter:** Los reintentos de Celery hacia la DGII usan espera creciente aleatoria para evitar el baneo de IP al momento de recuperación del servicio del gobierno.
5. **Append-Only en auditoría:** La tabla de `auditoria` no admite `UPDATE` ni `DELETE` a nivel de base de datos. Solo `INSERT`.
6. **IP opcional en API-Key:** El campo `allowed_ips` es opcional para compatibilidad con IPs dinámicas de proveedores dominicanos (Claro, Altice, Wind).
7. **Scopes mínimos por token:** Un token de caja registradora nunca puede tocar certificados, secuencias administrativas ni pagos.

---

## 9. Tabla Unificada de Endpoints

### Autenticación

| Método | Ruta | Acceso | Estado |
|:---:|:---|:---:|:---:|
| `POST` | `/api/v1/auth/login/` | Público | ✅ Activo |
| `POST` | `/api/v1/auth/token/refresh/` | Público | ✅ Activo |
| `POST` | `/api/v1/auth/recover-password/` | Público | ✅ Activo |

### Usuarios

| Método | Ruta | Acceso | Estado |
|:---:|:---|:---:|:---:|
| `POST/GET` | `/api/v1/usuarios/` | JWT | ✅ Activo |
| `GET/PATCH` | `/api/v1/usuarios/me/` | JWT | ✅ Activo |
| `POST` | `/api/v1/usuarios/me/change-password/` | JWT | ✅ Activo |

### Empresas

| Método | Ruta | Acceso | Estado |
|:---:|:---|:---:|:---:|
| `POST/GET` | `/api/v1/empresas/` | JWT / API-Key | ✅ Activo |
| `GET` | `/api/v1/empresas/{id}/` | JWT / API-Key | ✅ Activo |
| `GET` | `/api/v1/empresas/{id}/suscripcion/` | JWT | ✅ Activo |
| `GET` | `/api/v1/empresas/{id}/comprobantes/` | JWT | ✅ Activo |

### Planes, Suscripciones y Paquetes

| Método | Ruta | Acceso | Estado |
|:---:|:---|:---:|:---:|
| `POST/GET` | `/api/v1/planes/` | JWT | ✅ Activo |
| `POST/GET` | `/api/v1/suscripciones/` | JWT | ✅ Activo |
| `POST/GET` | `/api/v1/paquetes/` | JWT | ✅ Activo |

### API Keys

| Método | Ruta | Acceso | Estado |
|:---:|:---|:---:|:---:|
| `POST/GET` | `/api/v1/api-keys/` | JWT | ✅ Activo |
| `POST` | `/api/v1/api-keys/{id}/revocar/` | JWT | ✅ Activo |
| `POST` | `/api/v1/api-keys/{id}/rotar/` | JWT | ✅ Activo |

### Clientes (Directorio Fiscal Opcional)

| Método | Ruta | Acceso | Estado |
|:---:|:---|:---:|:---:|
| `POST/GET` | `/api/v1/clientes/` | JWT / API-Key | ✅ Activo |
| `GET/PATCH/DELETE` | `/api/v1/clientes/{rnc_cedula}/` | JWT / API-Key | ✅ Activo |

### Secuencias (Onboarding y Configuración)

| Método | Ruta | Acceso | Estado |
|:---:|:---|:---:|:---:|
| `POST` | `/api/v1/secuencias/` | API-Key (`empresa:onboarding`) | 🔧 Pendiente |
| `GET` | `/api/v1/secuenciales/` | JWT | ✅ Activo |
| `GET` | `/api/v1/secuenciales/{id}/preview/` | JWT | ✅ Activo |
| `POST` | `/api/v1/secuenciales/{id}/bloquear/` | JWT | ✅ Activo |
| `POST` | `/api/v1/secuenciales/{id}/desbloquear/` | JWT | ✅ Activo |

### Comprobantes

| Método | Ruta | Acceso | Estado |
|:---:|:---|:---:|:---:|
| `POST` | `/api/v1/comprobantes/` | API-Key (`comprobantes:emision`) | 🔧 Pendiente |
| `GET` | `/api/v1/comprobantes/` | JWT / API-Key | 🔧 Pendiente |
| `GET` | `/api/v1/comprobantes/{id}/` | JWT / API-Key | 🔧 Pendiente |
| `PATCH` | `/api/v1/comprobantes/{id}/` | JWT / API-Key (solo BORRADOR) | 🔧 Pendiente |

### Pagos

| Método | Ruta | Acceso | Estado |
|:---:|:---|:---:|:---:|
| `POST/GET` | `/api/v1/pagos/` | JWT | ✅ Activo |
| `PATCH` | `/api/v1/pagos/{id}/actualizar_confirmacion/` | JWT | ✅ Activo |
| `POST` | `/api/v1/pagos/{id}/rechazar/` | JWT | ✅ Activo |
| `GET` | `/api/v1/pagos/{id}/pdf/a4/` | JWT | ✅ Activo |
| `GET` | `/api/v1/pagos/{id}/pdf/80mm/` | JWT | ✅ Activo |
| `GET` | `/api/v1/pagos/historial/` | JWT | ✅ Activo |
| `POST` | `/api/v1/pagos/{id}/confirmar/` | JWT | ⚠️ Deprecated |

### Webhooks y DGII

| Método | Ruta | Acceso | Estado |
|:---:|:---|:---:|:---:|
| `GET` | `/api/v1/webhooks/` | JWT | 🔧 Pendiente |
| Cualquier | `/api/v1/dgii/` | N/A (interno) | 🔧 Pendiente |

---

## 10. Códigos de Error Comunes

| Status | Cuándo ocurre | Ejemplo |
|:---:|:---|:---|
| `400` | Validación matemática fallida | `{"monto_total": ["La sumatoria de líneas no coincide con el total declarado."]}` |
| `400` | Referencia faltante en pago no-EFECTIVO | `{"referencia": ["Obligatoria si el método no es EFECTIVO."]}` |
| `400` | PATCH sobre comprobante procesado | `{"detail": "Solo se puede modificar un comprobante en estado BORRADOR."}` |
| `401` | Sin JWT ni API-Key | `{"detail": "Authentication credentials were not provided."}` |
| `403` | API-Key revocada o scope insuficiente | `{"detail": "Invalid API key."}` |
| `403` | Rango de secuencia supera límite del plan | `{"detail": "El rango solicitado de 40 comprobantes excede el límite de su plan (Máximo 20)."}` |
| `403` | Empresa sin saldo de comprobantes | `{"detail": "Cuota de comprobantes agotada. Contacte a soporte DerejSoft."}` |
| `404` | Recurso no encontrado o de otra empresa | `{"detail": "Not found."}` |
| `409` | Cliente duplicado en la empresa | `{"rnc_cedula": ["Ya existe un cliente con este RNC/Cédula."]}` |

---

*Versión: 1.0.0 — Estado del backend al 31 de mayo de 2026*
*Basado en las decisiones arquitectónicas consolidadas del equipo DerejSoft*