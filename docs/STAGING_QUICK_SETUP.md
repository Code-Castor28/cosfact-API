# 🧪 Setup Rápido: Staging / Laboratorio (Ubuntu)

## 📌 Diferencias Staging vs Producción

| Aspecto | Staging | Producción |
|--------|---------|-----------|
| **Debug** | DEBUG=True (opcional) | DEBUG=False |
| **BD** | PostgreSQL local | PostgreSQL prod |
| **SSL** | Auto-signed | Let's Encrypt |
| **Workers** | 1-2 | 4+ |
| **Acceso** | Interna (VPN/LAN) | Público internet |
| **Backups** | Diario | Cada 6h |
| **Monitoreo** | Básico | Sentry + Datadog |
| **Logs** | Console | Archivos + ELK |

---

## ⚡ Setup Express (15 minutos)

### 1️⃣ Preparar máquina Ubuntu
```bash
# SSH a tu servidor
ssh usuario@ip-servidor

# Actualizar
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv postgresql redis-server nginx git

# Crear usuario
sudo useradd -m -s /bin/bash derejfact
sudo -i -u derejfact
```

### 2️⃣ Clonar y configurar app
```bash
cd /home/derejfact
git clone https://github.com/DerejSoft/derejfactAPI.git
cd derejfactAPI
git checkout principio

# Venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3️⃣ Configurar .env
```bash
# Editar el .env en /home/derejfact/derejfactAPI/.env
nano .env
```

```bash
# Mínimo para staging
SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
DEBUG=True
ALLOWED_HOSTS=tu-ip-o-dominio.com,localhost,127.0.0.1

DATABASE_URL=postgresql://derejfact:password@localhost:5432/derejfact_staging
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### 4️⃣ Crear base de datos
```bash
sudo -i -u postgres
psql
```

```sql
CREATE DATABASE derejfact_staging;
CREATE USER derejfact WITH PASSWORD 'password-staging';
GRANT ALL PRIVILEGES ON DATABASE derejfact_staging TO derejfact;
\q
```

### 5️⃣ Migraciones
```bash
python manage.py migrate
python manage.py createsuperuser  # Crear admin
```

### 6️⃣ Iniciar servicios (6 terminales simultáneas)

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: PostgreSQL (ya corre como servicio)
# sudo systemctl status postgresql

# Terminal 3: Django (Gunicorn o runserver)
gunicorn core.wsgi:application --bind 0.0.0.0:8000

# Terminal 4: Celery Worker
celery -A core worker --loglevel=info

# Terminal 5: Celery Beat
celery -A core beat --loglevel=info

# Terminal 6: Flower (Monitoreo, opcional)
pip install flower
celery -A core flower
```

### 7️⃣ Probar endpoints
```bash
# En otra terminal/máquina
curl http://tu-ip:8000/api/v1/auth/login/
curl http://tu-ip:5555  # Flower
```

---

## 🔧 Configuración systemd (Recomendado para Staging)

Seguir los archivos `.service` del documento **DEPLOY_UBUNTU.md** pero con nombres `-staging`:

```bash
sudo nano /etc/systemd/system/gunicorn-staging.service
sudo nano /etc/systemd/system/celery-worker-staging.service
sudo nano /etc/systemd/system/celery-beat-staging.service
```

Luego:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gunicorn-staging celery-worker-staging celery-beat-staging
sudo systemctl start gunicorn-staging celery-worker-staging celery-beat-staging
sudo systemctl status gunicorn-staging
```

---

## 🧪 Testing Manual del Flujo de Pagos

### 1. Crear datos de prueba
```bash
python manage.py shell
```

```python
from apps.empresas.models import Empresa
from apps.subscriptions.models import Plan, Suscripcion
from datetime import datetime, timedelta

# Crear empresa de prueba
empresa = Empresa.objects.create(
    rnc="123456789",
    razon_social="Empresa Test",
    nombre_comercial="Test Inc",
    ambiente="STAGING"
)

# Crear plan
plan = Plan.objects.create(
    nombre="Plan Test",
    precio=100.00,
    limite_comprobantes=1000
)

# Crear suscripción que vence en 10 días
suscripcion = Suscripcion.objects.create(
    empresa=empresa,
    plan=plan,
    estado="ACTIVA",
    fecha_renovacion=datetime.now() + timedelta(days=10)
)

print(f"✅ Empresa: {empresa.rnc}")
print(f"✅ Suscripción vence en: {suscripcion.fecha_renovacion}")
```

### 2. Ejecutar generador de pagos
```python
from apps.pagos.tasks import generar_pagos_automaticos

resultado = generar_pagos_automaticos()
print(resultado)
# {"status": "success", "pagos_creados": 1, "errores": 0, "total_procesadas": 1}
```

### 3. Verificar pago creado
```bash
curl -X GET http://localhost:8000/api/v1/pagos/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Debería retornar:
```json
{
  "count": 1,
  "results": [
    {
      "id": "uuid-xxx",
      "empresa_nombre": "Empresa Test",
      "monto": "100.00",
      "estado": "PENDIENTE",
      "metodo_pago": null,
      "referencia": null
    }
  ]
}
```

### 4. Confirmar pago
```bash
curl -X PATCH http://localhost:8000/api/v1/pagos/uuid-xxx/actualizar_confirmacion/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metodo_pago": "TRANSFERENCIA",
    "referencia": "TRF-12345",
    "observaciones": "Test"
  }'
```

Respuesta esperada:
```json
{
  "id": "uuid-xxx",
  "estado": "CONFIRMADO",
  "confirmado_por": "admin",
  "fecha_confirmacion": "2026-05-21T15:30:00Z"
}
```

---

## 📊 Monitoreo en Staging

### Ver logs en tiempo real
```bash
# Celery Worker
sudo journalctl -u celery-worker-staging.service -f

# Celery Beat
sudo journalctl -u celery-beat-staging.service -f

# Gunicorn
sudo journalctl -u gunicorn-staging.service -f
```

### Verificar tasks están registradas
```bash
celery -A core inspect registered
```

### Ver tasks activas
```bash
celery -A core inspect active
```

### Estadísticas
```bash
celery -A core inspect stats
```

---

## 🚨 Verificación Pre-Producción

Checklist antes de desplegar a producción:

- [ ] ✅ Tasks `generar_pagos_automaticos` se ejecutan correctamente
- [ ] ✅ Pagos se crean automáticamente 15 días antes del vencimiento
- [ ] ✅ Endpoint `/actualizar_confirmacion/` confirma pagos correctamente
- [ ] ✅ Suscripción se activa después de confirmación
- [ ] ✅ PaqueteComprobantes se crea automáticamente
- [ ] ✅ Historial de pagos se registra correctamente
- [ ] ✅ Beat scheduler ejecuta tareas a las 00:00 y 08:00
- [ ] ✅ Flower muestra tasks ejecutadas correctamente
- [ ] ✅ Logs limpios (no hay errores)
- [ ] ✅ Redis está persistente
- [ ] ✅ PostgreSQL está en modo producción (fsync=on)
- [ ] ✅ SSL/TLS configurado
- [ ] ✅ DEBUG=False en settings.production
- [ ] ✅ Backups configurados
- [ ] ✅ Monitoreo de alertas (Sentry, etc)

---

## 🔄 Flujo de Actualización

Si necesitas actualizar el código en staging:

```bash
cd /home/derejfact/derejfactAPI
source venv/bin/activate

# Traer cambios
git pull origin principio

# Instalar dependencias nuevas (si hay)
pip install -r requirements.txt

# Migraciones
python manage.py migrate

# Recolectar estáticos
python manage.py collectstatic --no-input

# Reiniciar servicios
sudo systemctl restart gunicorn-staging
sudo systemctl restart celery-worker-staging
sudo systemctl restart celery-beat-staging
```

---

## 📞 Soporte

Si algo no funciona:

1. **Revisar logs**: `sudo journalctl -u SERVICE_NAME -n 50`
2. **Verificar Redis**: `redis-cli ping`
3. **Verificar PostgreSQL**: `psql -U derejfact -d derejfact_staging -c "SELECT 1"`
4. **Verificar tasks**: `celery -A core inspect registered`
5. **Restart**: `sudo systemctl restart SERVICIO`

---

**¿Listo para desplegar?** → Ver `DEPLOY_UBUNTU.md` para producción
