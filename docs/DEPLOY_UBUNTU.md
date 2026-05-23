# 🚀 Deploy Celery en Ubuntu Server (Producción & Staging)

## 📍 Escenarios Cubiertos
- **Laboratorio/Staging**: Test antes de producción
- **Producción**: Ubuntu Server 20.04+ LTS
- **Público**: API accesible desde internet

---

## 🏗️ Arquitectura Recomendada

```
┌─────────────────┐
│  Internet       │
│  (Clientes)     │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Nginx (Proxy)  │ ← Reverse proxy + SSL
└────────┬────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│  Ubuntu Server 20.04 LTS                 │
├──────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────┐   │
│  │ Gunicorn    │  │ Celery Worker   │   │
│  │ (Django)    │  │ (Background)    │   │
│  └─────────────┘  └─────────────────┘   │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  Celery Beat (Scheduler)         │   │
│  │  - 00:00: generar_pagos          │   │
│  │  - 08:00: notificar_pagos        │   │
│  └──────────────────────────────────┘   │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  Redis (localhost:6379)          │   │
│  │  - Broker + Result Backend       │   │
│  └──────────────────────────────────┘   │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  PostgreSQL (localhost:5432)     │   │
│  │  - Base de datos                 │   │
│  └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

---

## 📦 Paso 1: Preparar Ubuntu Server

### 1.1 Actualizar sistema
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential python3.11 python3.11-venv python3.11-dev \
  redis-server postgresql postgresql-contrib nginx supervisor curl git
```

### 1.2 Crear usuario no-root para la aplicación
```bash
sudo useradd -m -s /bin/bash derejfact
sudo usermod -aG sudo derejfact
sudo -i -u derejfact
```

### 1.3 Configurar variables de entorno globales
```bash
sudo nano /etc/environment
```
Agregar:
```bash
DJANGO_SETTINGS_MODULE=core.settings.production
SECRET_KEY="your-super-secret-key-here"
DEBUG=False
ALLOWED_HOSTS="tu-dominio.com,api.tu-dominio.com"
DATABASE_URL="postgresql://derejfact:password@localhost:5432/derejfact"
CELERY_BROKER_URL="redis://localhost:6379/0"
CELERY_RESULT_BACKEND="redis://localhost:6379/1"
FERNET_KEY="your-fernet-key"
```

Recargar:
```bash
source /etc/environment
```

---

## 🗄️ Paso 2: Configurar Base de Datos (PostgreSQL)

### 2.1 Crear base de datos
```bash
sudo -i -u postgres
psql
```

```sql
CREATE DATABASE derejfact;
CREATE USER derejfact WITH PASSWORD 'password-seguro-aqui';
ALTER ROLE derejfact SET client_encoding TO 'utf8';
ALTER ROLE derejfact SET default_transaction_isolation TO 'read committed';
ALTER ROLE derejfact SET default_transaction_deferrable TO on;
ALTER ROLE derejfact SET default_transaction_deferrable TO on;
GRANT ALL PRIVILEGES ON DATABASE derejfact TO derejfact;
\q
```

### 2.2 Verificar conexión
```bash
psql -U derejfact -d derejfact -c "SELECT 1"
```

---

## 📦 Paso 3: Clonar y configurar aplicación

### 3.1 Clonar repositorio
```bash
sudo -i -u derejfact
cd /home/derejfact
git clone https://github.com/DerejSoft/derejfactAPI.git
cd derejfactAPI
git checkout principio  # o rama de producción
```

### 3.2 Crear venv e instalar dependencias
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 3.3 Ejecutar migraciones
```bash
python manage.py migrate --settings=core.settings.production
python manage.py collectstatic --no-input --settings=core.settings.production
```

### 3.4 Crear superuser (opcional)
```bash
python manage.py createsuperuser --settings=core.settings.production
```

---

## 🟠 Paso 4: Configurar Redis

### 4.1 Verificar Redis está activo
```bash
sudo systemctl status redis-server
sudo systemctl enable redis-server  # Auto-start en boot
sudo systemctl start redis-server
```

### 4.2 Verificar conexión
```bash
redis-cli ping
# Debería retornar: PONG
```

### 4.3 Optimizar Redis para producción (Opcional)
```bash
sudo nano /etc/redis/redis.conf
```

Buscar y cambiar:
```conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

Reiniciar Redis:
```bash
sudo systemctl restart redis-server
```

---

## 🎯 Paso 5: Configurar Gunicorn (Django App Server)

### 5.1 Crear archivo systemd para Gunicorn
```bash
sudo nano /etc/systemd/system/gunicorn-derejfact.service
```

Agregar:
```ini
[Unit]
Description=Gunicorn application server for DerejFact
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=notify
User=derejfact
Group=www-data
WorkingDirectory=/home/derejfact/derejfactAPI
Environment="PATH=/home/derejfact/derejfactAPI/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=core.settings.production"
EnvironmentFile=/etc/environment
ExecStart=/home/derejfact/derejfactAPI/venv/bin/gunicorn \
    --workers 4 \
    --worker-class sync \
    --bind unix:/run/gunicorn-derejfact.sock \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    core.wsgi:application

ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
KillSignal=SIGTERM

Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

### 5.2 Iniciar Gunicorn
```bash
sudo systemctl daemon-reload
sudo systemctl enable gunicorn-derejfact.service
sudo systemctl start gunicorn-derejfact.service
sudo systemctl status gunicorn-derejfact.service
```

### 5.3 Verificar socket
```bash
ls -la /run/gunicorn-derejfact.sock
```

---

## ⚙️ Paso 6: Configurar Celery Worker

### 6.1 Crear archivo systemd para Worker
```bash
sudo nano /etc/systemd/system/celery-worker-derejfact.service
```

Agregar:
```ini
[Unit]
Description=Celery Worker for DerejFact
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=forking
User=derejfact
Group=www-data
WorkingDirectory=/home/derejfact/derejfactAPI
Environment="PATH=/home/derejfact/derejfactAPI/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=core.settings.production"
EnvironmentFile=/etc/environment

ExecStart=/home/derejfact/derejfactAPI/venv/bin/celery -A core worker \
    --loglevel=info \
    --concurrency=4 \
    --pool=prefork \
    --logfile=/var/log/celery/worker-derejfact.log \
    --pidfile=/var/run/celery/worker-derejfact.pid

ExecReload=/bin/kill -s HUP $MAINPID
KillMode=process
KillSignal=SIGTERM

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

### 6.2 Crear directorios de logs
```bash
sudo mkdir -p /var/log/celery /var/run/celery
sudo chown derejfact:www-data /var/log/celery /var/run/celery
sudo chmod 755 /var/log/celery /var/run/celery
```

### 6.3 Iniciar Worker
```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-worker-derejfact.service
sudo systemctl start celery-worker-derejfact.service
sudo systemctl status celery-worker-derejfact.service
```

### 6.4 Ver logs en tiempo real
```bash
sudo tail -f /var/log/celery/worker-derejfact.log
```

---

## ⏰ Paso 7: Configurar Celery Beat Scheduler

### 7.1 Crear archivo systemd para Beat
```bash
sudo nano /etc/systemd/system/celery-beat-derejfact.service
```

Agregar:
```ini
[Unit]
Description=Celery Beat Scheduler for DerejFact
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=derejfact
Group=www-data
WorkingDirectory=/home/derejfact/derejfactAPI
Environment="PATH=/home/derejfact/derejfactAPI/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=core.settings.production"
EnvironmentFile=/etc/environment

ExecStart=/home/derejfact/derejfactAPI/venv/bin/celery -A core beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --logfile=/var/log/celery/beat-derejfact.log \
    --pidfile=/var/run/celery/beat-derejfact.pid

ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

### 7.2 Instalar django-celery-beat (para schedules en DB)
```bash
sudo -i -u derejfact
cd /home/derejfact/derejfactAPI
source venv/bin/activate
pip install django-celery-beat
python manage.py migrate --settings=core.settings.production
```

### 7.3 Iniciar Beat
```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-beat-derejfact.service
sudo systemctl start celery-beat-derejfact.service
sudo systemctl status celery-beat-derejfact.service
```

### 7.4 Ver logs
```bash
sudo tail -f /var/log/celery/beat-derejfact.log
```

---

## 🌐 Paso 8: Configurar Nginx (Reverse Proxy)

### 8.1 Crear configuración de Nginx
```bash
sudo nano /etc/nginx/sites-available/derejfact
```

Agregar:
```nginx
upstream derejfact_app {
    server unix:/run/gunicorn-derejfact.sock fail_timeout=0;
}

server {
    listen 80;
    listen [::]:80;
    server_name tu-dominio.com api.tu-dominio.com;

    # Redireccionar HTTP a HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name tu-dominio.com api.tu-dominio.com;

    # Certificados SSL (usar Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/tu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tu-dominio.com/privkey.pem;

    # Configuración SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Logs
    access_log /var/log/nginx/derejfact_access.log;
    error_log /var/log/nginx/derejfact_error.log;

    # Tamaño máximo de upload
    client_max_body_size 50M;

    # Configuración de proxy
    location / {
        proxy_pass http://derejfact_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Archivos estáticos
    location /static/ {
        alias /home/derejfact/derejfactAPI/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /home/derejfact/derejfactAPI/media/;
        expires 7d;
    }

    # Health check
    location /health/ {
        access_log off;
        return 200 "OK";
    }
}
```

### 8.2 Activar sitio
```bash
sudo ln -s /etc/nginx/sites-available/derejfact /etc/nginx/sites-enabled/
sudo nginx -t  # Verificar sintaxis
sudo systemctl restart nginx
```

### 8.3 Configurar SSL con Let's Encrypt
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot certonly --nginx -d tu-dominio.com -d api.tu-dominio.com
```

---

## 🔍 Paso 9: Configurar Monitoreo (Flower)

### 9.1 Crear archivo systemd para Flower
```bash
sudo nano /etc/systemd/system/flower-derejfact.service
```

Agregar:
```ini
[Unit]
Description=Flower Monitor for Celery
After=redis-server.service

[Service]
Type=simple
User=derejfact
Group=www-data
WorkingDirectory=/home/derejfact/derejfactAPI
Environment="PATH=/home/derejfact/derejfactAPI/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=core.settings.production"
EnvironmentFile=/etc/environment

ExecStart=/home/derejfact/derejfactAPI/venv/bin/celery -A core flower \
    --port=5555 \
    --address=127.0.0.1 \
    --logfile=/var/log/celery/flower-derejfact.log

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

### 9.2 Proteger Flower con contraseña (Nginx)
```bash
sudo nano /etc/nginx/sites-available/derejfact
```

Agregar bloque:
```nginx
server {
    listen 443 ssl http2;
    server_name flower.tu-dominio.com;
    
    ssl_certificate /etc/letsencrypt/live/tu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tu-dominio.com/privkey.pem;

    # Autenticación HTTP Basic
    auth_basic "Flower Admin";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:5555;
        proxy_set_header Host $host;
    }
}
```

Crear archivo de contraseña:
```bash
sudo htpasswd -c /etc/nginx/.htpasswd admin
sudo systemctl restart nginx
```

### 9.3 Iniciar Flower
```bash
sudo systemctl enable flower-derejfact.service
sudo systemctl start flower-derejfact.service
```

Accede a: https://flower.tu-dominio.com (usuario: admin)

---

## 📊 Paso 10: Configurar Logs y Rotación

### 10.1 Configurar logrotate para Celery
```bash
sudo nano /etc/logrotate.d/celery-derejfact
```

Agregar:
```
/var/log/celery/*-derejfact.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 derejfact www-data
    sharedscripts
    postrotate
        systemctl reload celery-worker-derejfact >/dev/null 2>&1 || true
    endscript
}
```

### 10.2 Configurar logrotate para Nginx
```bash
sudo nano /etc/logrotate.d/nginx
```

Actualizar con:
```
/var/log/nginx/derejfact_*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload nginx >/dev/null 2>&1 || true
    endscript
}
```

---

## ✅ Verificar Todo Está Corriendo

```bash
# Verificar servicios
sudo systemctl status gunicorn-derejfact.service
sudo systemctl status celery-worker-derejfact.service
sudo systemctl status celery-beat-derejfact.service
sudo systemctl status nginx
sudo systemctl status redis-server
sudo systemctl status postgresql

# Ver logs en tiempo real
sudo journalctl -u celery-worker-derejfact.service -f
sudo journalctl -u celery-beat-derejfact.service -f
sudo tail -f /var/log/nginx/derejfact_access.log

# Verificar Redis
redis-cli ping
redis-cli INFO memory

# Verificar Celery tasks registradas
celery -A core inspect registered
celery -A core inspect active_queues
```

---

## 🚀 Comandos Útiles en Producción

### Reiniciar servicios
```bash
sudo systemctl restart gunicorn-derejfact.service
sudo systemctl restart celery-worker-derejfact.service
sudo systemctl restart celery-beat-derejfact.service
```

### Ver estado de tasks
```bash
celery -A core inspect active
celery -A core inspect stats
```

### Purgar cola (cuidado)
```bash
celery -A core purge
```

### Ejecutar task manualmente
```bash
cd /home/derejfact/derejfactAPI
source venv/bin/activate
python manage.py shell --settings=core.settings.production
from apps.pagos.tasks import generar_pagos_automaticos
generar_pagos_automaticos()
```

### Ver workers conectados
```bash
celery -A core inspect ping
```

---

## 🔒 Checklist de Seguridad

- [ ] ✅ Cambiar contraseña PostgreSQL (no usar default)
- [ ] ✅ SSL/TLS activado en Nginx
- [ ] ✅ Firewall activo: `sudo ufw enable`
- [ ] ✅ Puertos abiertos solo necesarios:
  ```bash
  sudo ufw allow 22/tcp
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw allow 5432/tcp from 127.0.0.1  # Solo local
  sudo ufw allow 6379/tcp from 127.0.0.1  # Solo local
  ```
- [ ] ✅ DEBUG = False en settings.production
- [ ] ✅ SECRET_KEY generada aleatoria
- [ ] ✅ Backups diarios de BD
- [ ] ✅ Monitoreo de logs
- [ ] ✅ Alertas por email si task falla

---

## 📈 Escalabilidad Futura

Si necesitas más capacidad:

1. **Múltiples Workers**: Crear más instancias de `celery-worker-derejfact-2.service`, etc.
2. **Redis Cluster**: Para alta disponibilidad
3. **PostgreSQL Replica**: Para lectura distribuida
4. **Load Balancer**: Nginx upstream con múltiples Gunicorn
5. **Kubernetes**: Migrar a K8s si crece mucho

---

## 🆘 Troubleshooting

### Beat no ejecuta tasks a las 00:00
```bash
sudo systemctl restart celery-beat-derejfact.service
sudo tail -f /var/log/celery/beat-derejfact.log
```

### Worker no ve tasks
```bash
celery -A core inspect registered
```

### Redis no se conecta
```bash
sudo systemctl restart redis-server
redis-cli ping
```

### Gunicorn status 502 Bad Gateway
```bash
sudo journalctl -u gunicorn-derejfact.service -n 50
sudo systemctl restart gunicorn-derejfact.service
```

### Logs de error en Celery
```bash
sudo journalctl -u celery-worker-derejfact.service -n 100 --no-pager
```

---

## 📞 Soporte & Monitoring

Sugerencias:
- Instalar **Sentry** para rastrear errores: https://sentry.io
- Instalar **New Relic** o **Datadog** para monitoreo
- Configurar **uptime monitoring**: https://uptime.com
- Alertas por email/Slack para fallos de tasks

---

## 🎯 Próximos Pasos

1. ✅ Desplegar en staging (mismo procedimiento)
2. ✅ Probar flujo completo de pagos
3. ✅ Monitorear logs durante 24h
4. ✅ Verificar tasks se ejecutan a las 00:00 y 08:00
5. ✅ Desplegar en producción
