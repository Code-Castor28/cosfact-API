# PLAN DE EJECUCIÓN — FASE 2 (Emisión + Webhooks + Storage)

## 📋 ESTADO ACTUAL

- Fase 1 completada: modelos expandidos, cliente CRUD, certificado digital, refactor DGII services
- `apps/comprobantes/`: models.py listo, pero serializers.py, services.py, views.py, urls.py vacíos
- `apps/dgii/services.py`: `emitir_ecf()` existe pero sin endpoint HTTP que lo invoque
- `apps/webhooks/`: models.py listo (Webhook, WebhookEntrega), views/serializers/urls vacíos
- Storage: XML se guarda en disco local (`/var/derejfact/xmls/`), no hay config STORAGES

---

## 🏗️ BLOQUES DE EJECUCIÓN

---

### BLOQUE 0: Serializers + Views de Comprobantes

**Archivos:** `apps/comprobantes/serializers.py`, `views.py`, `urls.py`, `services.py`

#### 0.1 `ComprobanteSerializer`

- Campos: todos los del modelo excepto los internos (id, empresa, encf, track_id_dgii, estado, xml_path, xml_hash, intentos_envio, ultimo_error)
- Read-only: id, empresa, encf, track_id_dgii, estado, xml_path, xml_hash, intentos_envio, ultimo_error, creado_at, actualizado_at
- Validaciones extra:
  - `rnc_comprador`: 11 dígitos si se envía
  - `tipo_ecf`: solo 31, 32, 33, 34, 41 (igual que `clean()`)
  - `ncf_modificado`: obligatorio si tipo_ecf es 33 o 34
  - `codigo_modificacion`: 1-5 si tipo_ecf es 33 o 34
  - `email`: opcional, formato email si se envía

#### 0.2 `ComprobanteDetalleSerializer` (inline)

- `numero_linea`, `descripcion`, `cantidad`, `precio_unitario`, `subtotal`
- Todos requeridos excepto `id`

#### 0.3 `ComprobanteCreateSerializer`

- Hereda de `ComprobanteSerializer`
- Añade `detalles` como lista anidada de `ComprobanteDetalleSerializer`
- `empresa` se setea automáticamente desde `request.user` (API-Key) o del body (JWT admin)
- `estado` inicial siempre `BORRADOR`
- Opcional: `emitir_inmediatamente` (bool, default False) — si True, tras crear lanza emisión

#### 0.4 Vista `ComprobanteViewSet`

```python
class ComprobanteViewSet(viewsets.ModelViewSet):
    serializer_class = ComprobanteSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        return Comprobante.objects.filter(empresa=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return ComprobanteCreateSerializer
        return ComprobanteSerializer

    def perform_create(self, serializer):
        comprobante = serializer.save(
            empresa=self.request.user,
            estado=Comprobante.ESTADO_BORRADOR,
        )
        emitir_inmediatamente = serializer.validated_data.pop('emitir_inmediatamente', False)
        if emitir_inmediatamente:
            transaction.on_commit(lambda: emitir_ecf.delay(str(comprobante.id)))
```

**Endpoints:**

| Método | URL | Descripción |
|--------|-----|-------------|
| `POST` | `/api/v1/comprobantes/` | Crear comprobante (borrador) |
| `POST` | `/api/v1/comprobantes/` con `emitir_inmediatamente=true` | Crear y encolar emisión |
| `GET` | `/api/v1/comprobantes/` | Listar (filtrado por empresa) |
| `GET` | `/api/v1/comprobantes/{id}/` | Detalle |
| `PATCH` | `/api/v1/comprobantes/{id}/` | Actualizar borrador |
| `POST` | `/api/v1/comprobantes/{id}/emitir/` | Emitir un borrador existente |
| `GET` | `/api/v1/comprobantes/{id}/xml/` | Descargar XML firmado |
| `GET` | `/api/v1/comprobantes/{id}/pdf/` | Descargar PDF |

#### 0.5 URL registration

```python
# apps/comprobantes/urls.py
urlpatterns = [
    path('comprobantes/', ComprobanteViewSet.as_view({
        'get': 'list', 'post': 'create',
    }), name='comprobante-list'),
    path('comprobantes/<uuid:pk>/', ComprobanteViewSet.as_view({
        'get': 'retrieve', 'patch': 'partial_update',
    }), name='comprobante-detail'),
    path('comprobantes/<uuid:pk>/emitir/', comprobante_emitir, name='comprobante-emitir'),
    path('comprobantes/<uuid:pk>/xml/', comprobante_xml, name='comprobante-xml'),
    path('comprobantes/<uuid:pk>/pdf/', comprobante_pdf, name='comprobante-pdf'),
]
```

#### 0.6 `emitir_ecf` como tarea Celery

```python
# apps/comprobantes/services.py
@shared_task(bind=True, max_retries=5)
def emitir_ecf(self, comprobante_id):
    from dgii.services import emitir_ecf as emitir
    try:
        emitir(comprobante_id)
    except Exception as exc:
        countdowns = [30, 120, 600, 3600, 14400]
        intento = min(self.request.retries, len(countdowns) - 1)
        raise self.retry(exc=exc, countdown=countdowns[intento])

@shared_task(bind=True, max_retries=3)
def consultar_estado_dgii(self, comprobante_id):
    from dgii.services import consultar_estado
    comprobante = consultar_estado(comprobante_id)
    return comprobante.estado
```

---

### BLOQUE 1: XSD Validation

**Archivo:** `apps/dgii/utils/xsd_validator.py` (nuevo)

#### 1.1 Estructura

```
apps/dgii/utils/xsd_validator.py
apps/dgii/utils/xsd/                   # directorio con schemas DGII
├── ECF31.xsd
├── ECF32.xsd
├── ECF33.xsd
├── ECF34.xsd
├── ECF41.xsd
└── common.xsd
```

#### 1.2 Validador

```python
from lxml import etree

class XSDValidationError(Exception):
    pass

def validar_contra_xsd(xml_bytes: bytes, tipo_ecf: int) -> list:
    """
    Valida XML contra el schema XSD correspondiente al tipo_ecf.
    Retorna lista de errores (vacia si OK).
    ```
    xsd_path = Path(__file__).parent / "xsd" / f"ECF{tipo_ecf}.xsd"
    with open(xsd_path) as f:
        schema_root = etree.parse(f)
    schema = etree.XMLSchema(schema_root)
    doc = etree.fromstring(xml_bytes)
    if schema.validate(doc):
        return []
    return [str(e) for e in schema.error_log]
```

#### 1.3 Integración en `build_ecf_xml`

- Antes de retornar el XML, validar contra XSD
- Si hay errores, lanzar `XSDValidationError` con el detalle

#### 1.4 XSD placeholder

Por ahora crear validadores dummy que siempre retornan lista vacía, documentando que los XSD reales deben descargarse del portal DGII y colocarse en `xsd/`.

---

### BLOQUE 2: Emitir Endpoint + Pipeline Completo

**Archivo:** `apps/comprobantes/views.py`

#### 2.1 Action `emitir`

```python
@action(detail=True, methods=['post'])
def emitir(self, request, pk=None):
    comprobante = self.get_object()
    if comprobante.estado != Comprobante.ESTADO_BORRADOR:
        return Response(
            {"error": "Solo borradores pueden emitirse"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    transaction.on_commit(lambda: emitir_ecf.delay(str(comprobante.id)))
    return Response(
        {"mensaje": "Emisión encolada", "comprobante_id": str(comprobante.id)},
        status=status.HTTP_202_ACCEPTED,
    )
```

#### 2.2 Action `xml`

```python
@action(detail=True, methods=['get'])
def xml(self, request, pk=None):
    comprobante = self.get_object()
    if not comprobante.xml_path or not os.path.exists(comprobante.xml_path):
        return Response({"error": "XML no disponible"}, status=404)
    return FileResponse(
        open(comprobante.xml_path, 'rb'),
        filename=f"{comprobante.encf}.xml",
        content_type="application/xml",
    )
```

#### 2.3 Action `pdf`

- Si el comprobante está ACEPTADO, generar PDF usando reportlab
- Formato: A4 con datos del comprobante
- Si no hay datos suficientes, 400

#### 2.4 Pipeline de emisión completo

```
POST /api/v1/comprobantes/ (con emitir_inmediatamente=true)
  ↓
ComprobanteCreateSerializer → valida datos + detalles
  ↓
Crea Comprobante (estado=BORRADOR)
  ↓
transaction.on_commit → emitir_ecf.delay(comprobante_id)
  ↓
[ Celery worker ]
emitir_ecf(comprobante_id):
  1. select_for_update + marca PROCESANDO
  2. obtener_proximo_encf()
  3. build_ecf_xml() + XSD validation
  4. sign_xml() con CertificadoDigital
  5. _save_xml() (local o S3)
  6. DgiiClient.enviar_ecf()
  7. Actualiza estado según respuesta DGII
  ↓
Si falla: marca CONTINGENCIA, reintenta con backoff
Si éxito: marca ACEPTADO, dispara webhooks
```

---

### BLOQUE 3: Webhooks API + Delivery

#### 3.1 `apps/webhooks/serializers.py`

```python
class WebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webhook
        fields = ['id', 'nombre', 'url', 'eventos', 'estado', 'activo',
                  'ultimo_intento_at', 'ultimo_http_status', 'creado_at', 'actualizado_at']
        read_only_fields = ['id', 'estado', 'ultimo_intento_at',
                           'ultimo_http_status', 'creado_at', 'actualizado_at', 'secret_hash']
```

#### 3.2 `WebhookViewSet`

```python
class WebhookViewSet(viewsets.ModelViewSet):
    serializer_class = WebhookSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Webhook.objects.filter(empresa=self.request.user)

    def perform_create(self, serializer):
        webhook, secret = Webhook.crear(
            empresa=self.request.user,
            nombre=serializer.validated_data['nombre'],
            url=serializer.validated_data['url'],
            eventos=serializer.validated_data.get('eventos', []),
        )
        # Devolver secret UNA SOLA vez en la response
        return Response({
            **WebhookSerializer(webhook).data,
            "secret": secret,
        }, status=201)
```

**Endpoints:**

| Método | URL | Descripción |
|--------|-----|-------------|
| `POST` | `/api/v1/webhooks/` | Crear (devuelve secret una vez) |
| `GET` | `/api/v1/webhooks/` | Listar |
| `GET` | `/api/v1/webhooks/{id}/` | Detalle |
| `PATCH` | `/api/v1/webhooks/{id}/` | Actualizar |
| `DELETE` | `/api/v1/webhooks/{id}/` | Eliminar |
| `POST` | `/api/v1/webhooks/{id}/probar/` | Enviar evento de prueba |

#### 3.3 `apps/webhooks/services.py` (Delivery)

```python
import hashlib, hmac, json, requests
from django.conf import settings

def despachar_evento(webhook: Webhook, evento: str, payload: dict):
    """
    Crea WebhookEntrega y encola delivery vía Celery.
    """
    payload_json = json.dumps(payload, default=str).encode()
    payload_hash = hashlib.sha256(payload_json).hexdigest()
    entrega = WebhookEntrega.objects.create(
        webhook=webhook,
        evento=evento,
        payload_hash=payload_hash,
    )
    entregar_webhook.delay(str(entrega.id), payload_json.decode())

def firmar_payload(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

@shared_task(bind=True, max_retries=MAX_INTENTOS)
def entregar_webhook(self, entrega_id, payload_str):
    entrega = WebhookEntrega.objects.get(pk=entrega_id)
    webhook = entrega.webhook

    if not webhook.activo:
        return

    payload = payload_str.encode()
    signature = firmar_payload(payload, webhook.secret)  # ¿cómo obtenemos secret?
    # NOTA: secret no está almacenado (solo hash). Solución:
    # El cliente guarda el secret. Nosotros no podemos firmar sin él.
    # Alternativa: usar API Key como secreto compartido, o que el cliente
    # incluya el secret en la creación y lo guardemos cifrado como CertificadoDigital.pin_cifrado.

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": entrega.evento,
    }

    try:
        resp = requests.post(webhook.url, data=payload_str, headers=headers, timeout=10)
    except requests.RequestException as exc:
        entrega.estado = WebhookEntrega.ESTADO_FALLIDO
        entrega.error_mensaje = str(exc)[:2000]
        entrega.save()
        raise self.retry(countdown=60 * (self.request.retries + 1))

    if resp.status_code == 200:
        entrega.estado = WebhookEntrega.ESTADO_ENTREGADO
        entrega.ultimo_http_status = resp.status_code
        entrega.entregado_at = datetime.now(tz=timezone.utc)
        entrega.save()
    else:
        entrega.estado = WebhookEntrega.ESTADO_FALLIDO
        entrega.ultimo_http_status = resp.status_code
        entrega.error_mensaje = f"HTTP {resp.status_code}"
        entrega.save()
        if entrega.puede_reintentar:
            raise self.retry(countdown=60 * (self.request.retries + 1))
```

**Problema del secret:** El modelo actual guarda solo `secret_hash`. Para firmar el payload necesitamos el secret original. Soluciones:
- Opción A: Cifrar el secret con Fernet (como el PIN del certificado) y almacenarlo como `secret_cifrado` en Webhook
- Opción B: Usar la API Key de la empresa como HMAC secret compartido

**Decisión: Opción A** — agregar campo `secret_cifrado = models.TextField(blank=True)` a `Webhook`, cifrado con Fernet.

#### 3.4 Disparar webhooks al cambiar estado

En `apps/comprobantes/services.py` o mejor en `apps/dgii/services.py`, después de actualizar el estado:

```python
from webhooks.services import despachar_evento

# Después de marcar ACEPTADO:
for webhook in Webhook.objects.filter(empresa=comprobante.empresa, activo=True):
    if "comprobante.aceptado" in webhook.eventos:
        despachar_evento(webhook, "comprobante.aceptado", {
            "evento": "comprobante.aceptado",
            "comprobante_id": str(comprobante.id),
            "encf": comprobante.encf,
            "estado": comprobante.estado,
            "rnc_comprador": comprobante.rnc_comprador,
            "monto_total": str(comprobante.monto_total),
            "fecha_emision": comprobante.fecha_emision.isoformat(),
        })
```

---

### BLOQUE 4: Storage — Migración a S3/MinIO

#### 4.1 Agregar dependencia

```bash
pip install django-storages[boto3]
```

#### 4.2 Configuración en `core/settings/base.py`

```python
# ─── Storage (S3/MinIO) ─────────────────────────────────────────────────
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME')
AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL', default=None)  # Para MinIO
AWS_DEFAULT_ACL = 'private'
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
```

#### 4.3 Refactor `_save_xml()` en `dgii/services.py`

```python
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

def _save_xml(xml_bytes: bytes, path: str) -> str:
    """Guarda XML usando el storage configurado (local o S3)."""
    default_storage.save(path, ContentFile(xml_bytes))
    return hashlib.sha256(xml_bytes).hexdigest()
```

#### 4.4 Variable de entorno nueva

```
# .env
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_STORAGE_BUCKET_NAME=derejfact-xmls
AWS_S3_ENDPOINT_URL=http://localhost:9000
AWS_S3_REGION_NAME=us-east-1
```

#### 4.5 URLs firmadas para descarga

```python
def _xml_download_url(xml_path: str) -> str:
    if hasattr(default_storage, 'url'):
        return default_storage.url(xml_path)
    return xml_path
```

---

### BLOQUE 5: Tests

#### 5.1 `apps/comprobantes/tests.py` (nuevos)

| Test | Assert |
|------|--------|
| Crear comprobante vía POST | 201 |
| Crear con `emitir_inmediatamente=true` | 202 + tarea encolada |
| Crear sin API-Key | 401 |
| GET list comprobantes | 200 + lista |
| GET detalle comprobante | 200 + datos |
| PATCH borrador | 200 |
| POST emitir sobre borrador | 202 |
| POST emitir sobre ACEPTADO | 400 |
| GET xml sin XML guardado | 404 |
| GET xml con XML | 200 + content-type |
| Validación E31 sin rnc_comprador | 400 |
| Validación E33 sin ncf_modificado | 400 |
| Detalles inline en creación | 201 + detalles creados |

#### 5.2 `apps/webhooks/tests.py`

| Test | Assert |
|------|--------|
| Crear webhook vía API | 201 + secret en response |
| Crear sin secret en response posterior | secret oculto |
| GET list webhooks | 200 |
| PATCH webhook | 200 |
| DELETE webhook | 204 |
| Crear con URL http:// | 400 (debe ser https) |
| Evento inválido | 400 |
| POST probar webhook | 202 + entrega creada |
| Despachar evento y ver entrega | entrega en PENDIENTE |

#### 5.3 `apps/dgii/tests.py` (nuevos o existentes)

| Test | Assert |
|------|--------|
| XSD validation con XML válido | [] (sin errores) |
| XSD validation con XML inválido | lista de errores |
| Storage save y url | archivo guardado y accesible |

---

### BLOQUE 6: Router + URLs

#### 6.1 Agregar `ComprobanteViewSet` al router central

```python
# core/api_router.py
from comprobantes.views import ComprobanteViewSet
router.register(r'comprobantes', ComprobanteViewSet, basename='comprobante')
```

#### 6.2 Registrar `WebhookViewSet`

```python
from webhooks.views import WebhookViewSet
router.register(r'webhooks', WebhookViewSet, basename='webhook')
```

#### 6.3 Limpiar `core/urls.py`

- Remover `path('api/v1/', include('comprobantes.urls'))` si ya se maneja por router
- Remover `path('api/v1/', include('webhooks.urls'))` si ya se maneja por router

---

## 📐 NOTAS DE IMPLEMENTACIÓN

### Dependencias entre bloques

1. Bloque 2 (emitir endpoint) depende de Bloque 0 (serializers/views) y Bloque 1 (XSD)
2. Bloque 3 (webhooks delivery) depende de que Bloque 2 dispare eventos al cambiar estado
3. Bloque 4 (storage) se puede hacer en paralelo con los demás

### Orden sugerido

```
Semana 1: Bloque 0 + Bloque 1 (serializers, views, XSD)
Semana 2: Bloque 2 (emitir endpoint + pipeline completo)
Semana 3: Bloque 3 (webhooks API + delivery + integración con emisión)
Semana 4: Bloque 4 (storage S3), Tests + fixes
```

### Seguridad

- `secret_cifrado` en Webhook se cifra con Fernet (misma `FERNET_KEY`)
- El secret original se retorna UNA VEZ en POST, nunca en GET/PATCH
- Las URLs de webhook deben ser HTTPS (validado en `clean()`)
- XML firmado se sirve con `FileResponse`, attachment download
- Los endpoints de emisión requieren API-Key con scope `comprobantes:crear`

### Tareas Celery nuevas

```python
app.conf.beat_schedule = {
    ...
    'consultar-estados-pendientes': {
        'task': 'comprobantes.consultar_estados_pendientes',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'default'},
    },
    'reintentar-webhooks-fallidos': {
        'task': 'webhooks.reintentar_entregas',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default'},
    },
}
```

---

## 📂 ESTRUCTURA FINAL ESPERADA

```
apps/
├── comprobantes/
│   ├── serializers.py          # NUEVO
│   ├── services.py             # NUEVO (tareas Celery)
│   ├── views.py                # MODIFICADO (ViewSet + actions)
│   └── urls.py                 # MODIFICADO (urlpatterns)
├── dgii/
│   ├── utils/
│   │   ├── xsd_validator.py    # NUEVO
│   │   └── xsd/                # NUEVO (schemas DGII)
│   └── services.py             # MODIFICADO (_save_xml usa storage)
├── webhooks/
│   ├── serializers.py          # NUEVO
│   ├── services.py             # NUEVO (delivery + tasks)
│   ├── views.py                # MODIFICADO (ViewSet)
│   └── urls.py                 # MODIFICADO
core/
├── api_router.py               # MODIFICADO (+comprobantes, +webhooks)
└── settings/
    └── base.py                 # MODIFICADO (+AWS/S3 settings)
```

## ✅ CRITERIOS DE ACEPTACIÓN

1. `POST /api/v1/comprobantes/` crea borrador y devuelve 201
2. `POST /api/v1/comprobantes/{id}/emitir/` encola emisión y devuelve 202
3. El pipeline completo (crear → emitir → XML → firmar → enviar DGII) funciona end-to-end
4. `GET /api/v1/comprobantes/{id}/xml/` descarga XML firmado
5. Webhooks: CRUD funcionando, delivery con HMAC, reintentos con backoff
6. Al cambiar estado de comprobante a ACEPTADO/RECHAZADO, se dispara webhook
7. Tests pasando (mínimo 20 nuevos)
8. XSD validation reporta errores descriptivos
