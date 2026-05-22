# ⚙️ Configuración de Celery - Guía Completa

## 📋 Resumen: Qué necesitas para que Celery funcione

| Componente | Desarrollo | Producción |
|-----------|-----------|-----------|
| **Broker (Message Queue)** | Redis local | Redis remoto / RabbitMQ |
| **Result Backend** | Redis local | Redis remoto |
| **Worker** | `celery -A core worker` | Supervisor / systemd |
| **Beat Scheduler** | `celery -A core beat` | Supervisor / systemd |
| **Paquetes Python** | ✅ Ya instalados (requirements.txt) | ✅ Ya instalados |
| **Variables de entorno** | ⚠️ **NECESARIO** | ⚠️ **NECESARIO** |

---

## 🚀 Paso 1: Instalar Redis (Development)

### Windows (Recomendado: Windows Subsystem for Linux WSL2)

**Opción A: WSL2 + Redis nativo**
```bash
# En WSL2 terminal
sudo apt update
sudo apt install redis-server
redis-server
```

**Opción B: Docker (Más limpio)**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**Opción C: Instalador Windows (Legacy)**
```bash
# Descargar desde: https://github.com/microsoftarchive/redis/releases
# O usar Chocolatey:
choco install redis
redis-server
```

### Verificar que Redis está corriendo
```bash
redis-cli ping
# Debería retornar: PONG
```

---

## 🔧 Paso 2: Configurar Variables de Entorno

Crear o editar archivo `.env` en la raíz del proyecto:

```bash
# .env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

**⚠️ IMPORTANTE:**
- Base de datos `0`: Broker (cola de mensajes)
- Base de datos `1`: Result Backend (resultados de tasks)
- En producción: Cambiar `localhost` por IP del servidor Redis

### Verificar la configuración
```bash
python manage.py shell
from django.conf import settings
print(settings.CELERY_BROKER_URL)
print(settings.CELERY_RESULT_BACKEND)
```

---

## 📦 Paso 3: Verificar Paquetes Python

**Ya están instalados en requirements.txt:**
```
celery==5.6.3
redis==7.4.0
kombu==5.6.2
```

Confirmar:
```bash
pip list | grep -i celery
pip list | grep -i redis
```

---

## ▶️ Paso 4: Iniciar Celery (Development)

### Terminal 1: Worker (Procesa tasks)
```bash
# Desde C:\Users\USER\Desktop\PROYECTOS\derejfactAPI
celery -A core worker --loglevel=info
```

**Salida esperada:**
```
 -------------- celery@LAPTOP-USER v5.6.3 (opalescent)
--- ***** -----
-- ******* ----
- *** --- * ---
- ** ---------- [config]
- ** ----------
- *** --- * --- OS:   Windows (native), arch: x86_64, impl: CPython
- ** ---------- Python 3.11.x (...)
- ** ---------- [queues]
- *** --- * --- celery: Exchange:celery(direct) binding:celery
- ** ----------
- *** --- * ---
 -------------- [tasks]
                 . apps.pagos.tasks.generar_pagos_automaticos
                 . apps.pagos.tasks.notificar_pagos_proximos

[2026-05-21 15:30:45,123: INFO/MainProcess] Connected to redis://localhost:6379/0
[2026-05-21 15:30:45,456: INFO/MainProcess] mingle: syncing with 1 nodes.
[2026-05-21 15:30:45,789: INFO/MainProcess] mingle: sync complete
[2026-05-21 15:30:45,912: INFO/MainProcess] celery@LAPTOP-USER ready.
```

### Terminal 2: Beat Scheduler (Ejecuta tasks periódicas)
```bash
celery -A core beat --loglevel=info
```

**Salida esperada:**
```
celery beat v5.6.3 (opalescent) is starting.
LocalTime -> 2026-05-21 15:31:00.000000
Configuration ->
    . broker -> redis://localhost:6379/0
    . loader -> celery.loaders.app.AppLoader
    . scheduler -> celery.beat.PersistentScheduler
    . db -> celeryd.db
    . logfile -> [stderr]@%DEBUG
    - pool -> Scheduler(...)

Scheduler Options:
    - MaxInterval -> 5.00 seconds
    - Schedule -> {'generar-pagos-automaticos': {'task': 'pagos.generar_pagos_automaticos', ...}

Schedule:
    Timezone: America/Santo_Domingo
    
    generar-pagos-automaticos (pagos.generar_pagos_automaticos) -> crontab(0, 0)
        Next run at 2026-05-22 00:00:00 [in 8 hours, 29 minutes]
        
    notificar-pagos-proximos (pagos.notificar_pagos_proximos) -> crontab(8, 0)
        Next run at 2026-05-21 08:00:00 [in 16 hours]
```

### Terminal 3: Django (API)
```bash
python manage.py runserver
```

---

## ✅ Paso 5: Probar que Celery Funciona

### Test 1: Ejecutar task manualmente
```bash
python manage.py shell
from apps.pagos.tasks import generar_pagos_automaticos
resultado = generar_pagos_automaticos.delay()  # Asincrónico
print(resultado.id)
```

O síncronamente (para debug):
```python
resultado = generar_pagos_automaticos()
print(resultado)  # {"status": "success", "pagos_creados": 2, ...}
```

### Test 2: Monitoreador Flower (Interfaz web)
```bash
pip install flower
celery -A core flower
```
Luego accede a http://localhost:5555

**Verás:**
- Workers activos
- Tasks ejecutadas
- Errores y logs
- Gráficos de performance

### Test 3: Verificar que tus tasks están registradas
```bash
celery -A core inspect registered
```

**Debería mostrar:**
```
{
  'celery@LAPTOP-USER': {
    'registered': [
      'apps.pagos.tasks.generar_pagos_automaticos',
      'apps.pagos.tasks.notificar_pagos_proximos',
      ...otras tasks de Django...
    ]
  }
}
```

---

## 🐛 Troubleshooting

### ❌ "Connection refused" a Redis
```
ConnectionError: Error -2 connecting to localhost:6379. Name or service not known.
```
**Solución:** Inicia Redis
```bash
redis-server  # O docker run -d -p 6379:6379 redis:7-alpine
redis-cli ping  # Debe retornar PONG
```

### ❌ Worker no ve las tasks
```
No tasks received
```
**Solución:** Verificar que tasks están en `apps/pagos/tasks.py` y que la app está en INSTALLED_APPS

### ❌ Beat scheduler no ejecuta a las 00:00
```
Next run at 2026-05-22 00:00:00 [never runs]
```
**Solución:** 
- Revisar que CELERY_TIMEZONE esté correcto (ahora es `America/Santo_Domingo`)
- Reiniciar beat: `celery -A core beat --schedule=celerybeat-schedule`

### ❌ `ModuleNotFoundError: No module named 'apps.pagos.tasks'`
**Solución:** 
1. Verificar que `apps/pagos/tasks.py` existe
2. Verificar que tiene `from celery import shared_task`
3. Verificar que las funciones tienen `@shared_task`
4. Ejecutar: `python manage.py shell` y `from apps.pagos.tasks import generar_pagos_automaticos`

### ❌ Task ejecuta pero no hace nada
**Solución:** En `development.py`, está:
```python
CELERY_TASK_ALWAYS_EAGER = True  # Ejecuta síncronamente
CELERY_TASK_EAGER_PROPAGATES = True
```
Esto es correcto para development (debug fácil). En producción debe ser False.

---

## 📍 Configuración Actual de Tu Proyecto

### ✅ Ya configurado en `core/celery.py`:
```python
app.conf.beat_schedule = {
    'generar-pagos-automaticos': {
        'task': 'pagos.generar_pagos_automaticos',
        'schedule': crontab(hour=0, minute=0),  # 00:00 diariamente
    },
    'notificar-pagos-proximos': {
        'task': 'pagos.notificar_pagos_proximos',
        'schedule': crontab(hour=8, minute=0),  # 08:00 diariamente
    },
}
```

### ✅ Ya configurado en `apps/pagos/tasks.py`:
```python
@shared_task(bind=True, max_retries=3)
def generar_pagos_automaticos(self):
    # Crea pagos automáticamente 15 días antes del vencimiento
    ...
```

### ✅ Ya configurado en `core/settings/base.py`:
```python
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')
CELERY_TIMEZONE = 'America/Santo_Domingo'
```

---

## 🏭 Producción: Systemd (Linux)

Crear archivo `/etc/systemd/system/celery-worker.service`:
```ini
[Unit]
Description=Celery Worker for DerejFact
After=network.target redis-server.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/home/app/derejfactAPI
ExecStart=/home/app/derejfactAPI/venv/bin/celery -A core worker --loglevel=info --concurrency=4

[Install]
WantedBy=multi-user.target
```

Iniciar:
```bash
sudo systemctl daemon-reload
sudo systemctl start celery-worker
sudo systemctl enable celery-worker  # Arrancar al boot
sudo systemctl status celery-worker
```

Lo mismo para beat scheduler en `/etc/systemd/system/celery-beat.service`.

---

## 📊 Monitor de Celery en Producción

```bash
pip install celery-events
celery -A core events
```

O usar Flower:
```bash
celery -A core flower --port=5555
```

Luego accede a `https://tu-servidor.com:5555`

---

## 🔒 Variables de Entorno en Producción

Actualizar `.env` (o variables de sistema):
```bash
# Redis remoto
CELERY_BROKER_URL=redis://user:password@redis.prod.com:6379/0
CELERY_RESULT_BACKEND=redis://user:password@redis.prod.com:6379/1

# RabbitMQ (alternativa)
CELERY_BROKER_URL=amqp://user:password@rabbitmq.prod.com:5672//
CELERY_RESULT_BACKEND=redis://redis.prod.com:6379/0
```

---

## ✨ Resumen Rápido: Inicio Local

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Worker
celery -A core worker --loglevel=info

# Terminal 3: Beat
celery -A core beat --loglevel=info

# Terminal 4: Django
python manage.py runserver

# Terminal 5 (Opcional): Flower
pip install flower
celery -A core flower
```

Luego verifica en:
- API: http://localhost:8000/api/v1/pagos/
- Flower: http://localhost:5555

---

## 📝 Checklist para Go Live

- [ ] ✅ Redis instalado y corriendo en producción
- [ ] ✅ Variables de entorno configuradas (CELERY_BROKER_URL, CELERY_RESULT_BACKEND)
- [ ] ✅ Workers iniciados vía systemd con auto-restart
- [ ] ✅ Beat scheduler iniciado vía systemd con auto-restart
- [ ] ✅ Flower instalado y monitoreando
- [ ] ✅ Logs configurados (stderr → archivo)
- [ ] ✅ Task max_retries configurado > 0
- [ ] ✅ Email de alertas si task falla
- [ ] ✅ Backups diarios de resultados de tasks
- [ ] ✅ Test: Ejecutar `generar_pagos_automaticos()` manualmente y verificar
