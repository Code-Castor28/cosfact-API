# 🔴 Sentry - Error Tracking & Monitoring

## Instalación y Configuración

He agregado **Sentry** a tu proyecto para rastrear errores en tiempo real, logging centralizado y monitoreo de performance.

---

## 📦 Paso 1: Agregar variables de entorno

Edita tu `.env`:

```bash
# ─── Sentry ──────────────────────────────────────────────────────
SENTRY_DSN=https://17e81c696a9a9f6352ec4091642c3168@o4511431518257152.ingest.us.sentry.io/4511431524417536
ENVIRONMENT=development  # Cambia a "staging" o "production"
APP_VERSION=1.0.0
```

El **DSN** ya lo tienes del Sentry Dashboard.

---

## ✅ Paso 2: Lo que ya está configurado

### 2.1 Instalado en requirements.txt
```
sentry-sdk==1.50.1
```

Instala:
```bash
pip install -r requirements.txt
```

### 2.2 Configurado en `core/settings/base.py`

```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

SENTRY_DSN = env('SENTRY_DSN', default=None)
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(...),
        ],
        traces_sample_rate=0.1,  # 10% sampling
        send_default_pii=True,   # Incluir datos de usuario
        environment=env('ENVIRONMENT'),
        release=env('APP_VERSION'),
    )
```

**Integraciones activas:**
- ✅ Django (requests, errors, signals)
- ✅ Celery (tasks, failures)
- ✅ Logging (Python logging → Sentry)

### 2.3 Ruta de debug en `core/urls.py`

```python
path('sentry-debug/', trigger_sentry_error) if settings.DEBUG else None,
```

Solo accesible en desarrollo.

### 2.4 Logging mejorado en `core/settings/development.py`

```python
LOGGING = {
    'handlers': {
        'sentry': {
            'level': 'ERROR',
            'class': 'sentry_sdk.integrations.logging.EventHandler',
        },
    },
    'loggers': {
        'apps': {
            'handlers': ['console', 'sentry'],
        },
        'celery': {
            'handlers': ['console', 'sentry'],
        },
    },
}
```

Todos los logs ERROR+ se envían a Sentry automáticamente.

---

## 🧪 Paso 3: Verificar que funciona

### 3.1 Trigger error de prueba (desarrollo)
```bash
# Inicia la aplicación
python manage.py runserver

# En otra terminal o navegador
curl http://localhost:8000/sentry-debug/
# O: http://localhost:8000/sentry-debug/
```

Debería ver:
```
ZeroDivisionError: division by zero
```

En Sentry verá un error "Issues → New":
```
ZeroDivisionError: integer division or modulo by zero
```

### 3.2 Enviar logs manualmente

```python
import logging

logger = logging.getLogger(__name__)

# Estos se envían a Sentry automáticamente
logger.info('User logged in successfully')
logger.warning('Rate limit approaching')
logger.error('Database connection failed')
```

### 3.3 Capturar excepciones

```python
import sentry_sdk

try:
    resultado = 1 / 0
except ZeroDivisionError as e:
    sentry_sdk.capture_exception(e)
    # Se envía a Sentry + continúa la ejecución
```

---

## 📊 Qué captura Sentry automáticamente

### Errores HTTP
- 500 errors (exceptions no manejadas)
- 404 errors (en logs si está configurado)
- Status codes 4xx/5xx

### Tasks Celery
- Task failures
- Task timeouts
- Task retries
- Excepciones en workers

### Breadcrumbs (contexto)
- Requests HTTP previos
- Database queries
- Log messages
- Cambios de estado
- User interactions

### Performance
- Request timing (cuánto tarda cada endpoint)
- Transaction traces (10% de requests)
- Database query spans
- External API calls

---

## 🎯 Configuración por Ambiente

### Desarrollo
```bash
SENTRY_DSN=https://...your-staging-dsn...
ENVIRONMENT=development
DEBUG=True
```

### Staging
```bash
SENTRY_DSN=https://...your-staging-dsn...
ENVIRONMENT=staging
DEBUG=False
```

### Producción
```bash
SENTRY_DSN=https://...your-production-dsn...
ENVIRONMENT=production
DEBUG=False
```

**Tip:** Usa diferentes proyectos en Sentry para cada ambiente (Dev/Staging/Prod). Así los errores están organizados.

---

## 🔍 Dashboard Sentry

Accede a: https://sentry.io/organizations/YOUR-ORG/issues/

### Secciones principales

**Issues**
- Lista de errores únicos
- Frequency (cuántas veces pasó)
- Trending (está aumentando o disminuyendo)
- Time range (últimas 24h, 7d, etc)

**Performance**
- Latencia de endpoints (P50, P95, P99)
- Slowest transactions
- Error rate trending

**Alerts**
- Alertas cuando un error ocurre N veces
- Email/Slack notifications
- Custom threshold rules

**Releases**
- Trackea qué versión introdujo cada bug
- Auto-associates commits/PRs
- Deployment timeline

---

## 📋 Configuración Avanzada (Opcional)

### Filtrar datos sensibles

En `core/settings/base.py`:

```python
sentry_sdk.init(
    dsn=SENTRY_DSN,
    before_send=lambda event, hint: None if event.get('user', {}).get('email') == 'admin@' else event,
)
```

### Sample rate (no enviar todo)

```python
sentry_sdk.init(
    dsn=SENTRY_DSN,
    traces_sample_rate=0.1,  # Solo 10% de requests
    profiles_sample_rate=0.05,  # Solo 5% de profiles
)
```

### Ignorar ciertos errores

```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=SENTRY_DSN,
    integrations=[DjangoIntegration(transaction_style='url')],
    ignore_errors=[
        KeyboardInterrupt,
        SystemExit,
        ConnectionResetError,
    ],
)
```

---

## 🚨 Alertas Recomendadas en Sentry

### 1. New Issue Alert
```
Alert when: A new issue is created
Notify: Email/Slack
```

### 2. Regression Alert
```
Alert when: An error occurrence increases by 100% in 24h
Notify: Slack #dev-errors
```

### 3. Error Rate Alert
```
Alert when: Error rate > 5% of all requests
Notify: Email + Sentry escalation
```

### 4. Performance Alert
```
Alert when: P95 latency > 2s
Notify: Slack #performance
```

---

## 📝 Logging en tu código

### Dentro de views/tasks
```python
import logging

logger = logging.getLogger(__name__)

def confirmar_pago(request, pago_id):
    try:
        pago = Pago.objects.get(id=pago_id)
        pago.confirm()
        logger.info(f"Pago {pago_id} confirmado por {request.user}")
        return Response({"status": "confirmed"})
    except Pago.DoesNotExist:
        logger.error(f"Pago {pago_id} no encontrado")
        sentry_sdk.capture_exception()
        return Response({"error": "Not found"}, status=404)
```

### En tasks Celery
```python
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task
def generar_pagos_automaticos():
    try:
        # ... lógica ...
        logger.info(f"Pagos generados: {count}")
    except Exception as e:
        logger.error(f"Error generando pagos: {str(e)}")
        raise  # Celery captura y envía a Sentry
```

---

## ✨ Caso de Uso Real: Rastrear Pagos

Dentro de `apps/pagos/views.py`:

```python
import sentry_sdk

class PagoViewSet(viewsets.ModelViewSet):
    
    @action(detail=True, methods=['patch'])
    def actualizar_confirmacion(self, request, pk=None):
        pago = self.get_object()
        
        with sentry_sdk.push_scope() as scope:
            scope.set_context("pago", {
                "id": str(pago.id),
                "empresa": pago.empresa.rnc,
                "monto": float(pago.monto),
                "metodo_pago": pago.metodo_pago,
            })
            
            try:
                # Confirmación
                serializer = PagoUpdateSerializer(pago, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                self._confirmar_pago_internamente(pago, request.user)
                
                logger.info(f"Pago confirmado: {pago.id}")
                return Response(serializer.data)
                
            except Exception as e:
                logger.error(f"Error confirmando pago: {str(e)}")
                scope.set_level("error")
                sentry_sdk.capture_exception(e)
                raise
```

En Sentry verás:
- Contexto: Empresa RNC, monto, método
- User: Quién confirmó
- Request: Headers, URL, método
- Breadcrumbs: Qué pasó antes del error

---

## 🔄 Integración con Celery

Sentry captura automáticamente:

```python
@shared_task
def generar_pagos_automaticos():
    # Si falla, Sentry:
    # - Captura la exception
    # - Registra el task_id
    # - Tracks retries
    # - Asocia a release/environment
    
    try:
        pagos = Pago.objects.filter(...)
        # ... procesamiento ...
    except Exception as e:
        # Sentry captura automáticamente
        raise
```

En Sentry verás en "Performance":
- Task timing
- Queue wait time
- Worker processing time

---

## 📞 Troubleshooting

### "No se envía nada a Sentry"
1. Verificar SENTRY_DSN en .env
2. Verificar `DEBUG=False` (en prod, no se envía si DEBUG=True)
3. Test: `curl http://localhost:8000/sentry-debug/`
4. Revisar logs de Django

### "Se envía todo, incluso warnings"
Cambiar en settings:
```python
LoggingIntegration(
    level=logging.WARNING,      # Captura >= WARNING (no INFO)
    event_level=logging.ERROR   # Envía como evento solo ERROR+
)
```

### "Error rate muy alto"
1. Filtrar errores 404, 401, etc
2. Ignorar ciertos tipos
3. Reducir `traces_sample_rate`

### "Demasiados eventos"
```python
before_send=lambda event, hint: event if event.get('level') != 'info' else None
```

---

## 📚 Siguiente Paso

Ahora que tienes Sentry:
1. ✅ Configura `.env` con tu SENTRY_DSN
2. ✅ Instala: `pip install -r requirements.txt`
3. ✅ Test: `python manage.py runserver` + `curl http://localhost:8000/sentry-debug/`
4. ✅ Verifica en Sentry dashboard
5. ✅ En producción, cambia ENVIRONMENT=production

**¿Preguntas?** Revisa https://docs.sentry.io/platforms/python/integrations/django/
