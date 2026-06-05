# DerejFact API
<p align="center">
  <img src="img-docs/logo-docs.png" alt="Banner del Proyecto" width="100%">
</p>
[![Deploy a Producción](https://github.com/DerejSoft/derejfactAPI/actions/workflows/deploy.yml/badge.svg)](https://github.com/DerejSoft/derejfactAPI/actions/workflows/deploy.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python)
![Django](https://img.shields.io/badge/Django-5.0-092E20?logo=django)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?logo=celery)
![Estado](https://img.shields.io/badge/Fases-31%2F31%20%E2%9C%85-brightgreen)

**Middleware multi-tenant de facturación electrónica (e-CF) para la República Dominicana.**  
API puente asíncrona, segura y multi-tenant que conecta sistemas POS con la DGII.

---

## Tabla de Contenidos

- [Descripción](#descripción)
- [Características](#características)
- [Stack Tecnológico](#stack-tecnológico)
- [Arquitectura](#arquitectura)
- [Inicio Rápido](#inicio-rápido)
- [Despliegue](#despliegue)
- [Estado del Proyecto](#estado-del-proyecto)
- [Licencia](#licencia)

---

## Descripción

DerejFact API es un SaaS de facturación electrónica que actúa como middleware entre los sistemas POS de los comercios y la Dirección General de Impuestos Internos (DGII) de República Dominicana.

Opera como motor de validación matemática, numeración atómica de e-NCF, firma criptográfica síncrona (PKCS#12) y pasarela de comunicación asíncrona con la DGII.

**Dos productos en uno:**
- **DerejFact API** — el servidor SaaS (este proyecto)
- **POS** — cliente externo que consume la API
- **Portal Admin** — panel de gestión web (proyecto separado)

---

## Características

- **Multi-tenant** — Aislamiento completo de datos por empresa (RNC)
- **Autenticación dual** — JWT para administradores, API Key con scopes para POS
- **Numeración atómica de e-NCF** — `SELECT FOR UPDATE` sin duplicados ni saltos
- **Firma XML PKCS#12** — PIN cifrado con Fernet, descifrado solo en memoria volátil
- **Máquina de estados inmutable** — Transiciones validadas, e-NCF viciados ante rechazo DGII
- **Webhooks con HMAC** — Notificaciones asíncronas al POS con reintentos
- **Cola de tareas Celery** — Envío asíncrono a DGII con backoff exponencial y jitter
- **Catálogos DGII** — Provincias, municipios, monedas, unidades de medida, formas de pago e impuestos adicionales editables vía admin
- **Auditoría append-only** — Registro inmutable de acciones críticas con firma HMAC

---

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Framework | Django 5.0 + Django REST Framework 3.17 |
| Base de datos | PostgreSQL |
| Cola de tareas | Celery 5.6 + Redis (broker) |
| Criptografía | `cryptography` (Fernet para PIN, PKCS#12 para firma XML) |
| XML/ SOAP | `lxml` + `xmlsec` |
| Autenticación humana | JWT (`djangorestframework-simplejwt`) |
| Autenticación POS | API Key personalizada con scopes |
| Servidor WSGI | Gunicorn |
| Proxy inverso | Nginx |
| Monitoreo | Sentry + Flower |

---

## Arquitectura

```
[POS — API Key]
      │
      ▼
┌──────────────────────────────────────────────────┐
│  Nginx (Reverse Proxy + SSL)                     │
└────────────────┬─────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────┐
│  Gunicorn (Django + DRF)                         │
│                                                   │
│  api-keys (Scope validation)                      │
│  suscripciones (Balance Guard)                    │
│  comprobantes (e-CF engine)                       │
│  dgii (XML Firma + SOAP DGII)                     │
│  webhooks (Notificaciones al POS)                 │
│  notificaciones (Correos humanos)                 │
│  audit (Append-only log)                          │
└───────┬────────────────────────────────┬──────────┘
        │                                │
        ▼                                ▼
┌───────────────┐              ┌──────────────────┐
│  PostgreSQL   │              │  Redis (Broker)   │
└───────────────┘              └────────┬─────────┘
                                        │
                                        ▼
                               ┌──────────────────┐
                               │  Celery Worker    │
                               │  ─ Envío SOAP DGII│
                               │  ─ Webhook retry  │
                               │  ─ Notificaciones │
                               └──────────────────┘
                                        │
                                        ▼
                               ┌──────────────────┐
                               │  DGII (SOAP/XML) │
                               │  testecf / ecf   │
                               └──────────────────┘
```

Para una descripción arquitectónica detallada, ver [`docs/arqui.md`](docs/arqui.md).

---

## Inicio Rápido

### Requisitos

- Python 3.11+
- PostgreSQL
- Redis

### Instalación

```bash
# Clonar
git clone https://github.com/DerejSoft/derejfactAPI.git
cd derejfactAPI

# Entorno virtual
python3 -m venv venv
source venv/bin/activate

# Dependencias
pip install -r requirements.txt

# Variables de entorno
# Editar .env con las credenciales locales

# Base de datos
python manage.py migrate
python manage.py createsuperuser

# Servidor de desarrollo
python manage.py runserver
```

### Celery (para tareas asíncronas)

```bash
# Terminal 1 — Worker
celery -A core worker -l info

# Terminal 2 — Beat (opcional, para tareas programadas)
celery -A core beat -l info
```

---

## Despliegue

El despliegue en producción usa **Ubuntu Server + Nginx + Gunicorn + PostgreSQL + Redis + Celery**.

### Resumen

```bash
# 1. Clonar y configurar
git clone https://github.com/DerejSoft/derejfactAPI.git
cd derejfactAPI
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Variables de entorno
export DJANGO_SETTINGS_MODULE=core.settings.production
export SECRET_KEY="..."
export DEBUG=False

# 3. Migrar y estáticos
python manage.py migrate
python manage.py collectstatic --no-input

# 4. Servicios systemd
# Gunicorn, Celery Worker, Celery Beat (ver docs/DEPLOY_UBUNTU.md)
```

**CI/CD:** El repositorio incluye un pipeline de GitHub Actions (`deploy.yml`) que despliega automáticamente a producción al hacer push a `main`, usando Tailscale para conexión segura.

Para la guía completa de instalación paso a paso, ver [`docs/DEPLOY_UBUNTU.md`](docs/DEPLOY_UBUNTU.md).

---

## Estado del Proyecto

| Fase | Estado |
|:-----|:------:|
| Fase 0 — Seguridad y Estabilidad | ✅ 6/6 |
| Fase 1a — Infraestructura (Scopes + Onboarding) | ✅ 2/2 |
| Fase 1b — Comprobantes CRUD | ✅ 4/4 |
| Fase 1c — Parches de Validación + Blindaje | ✅ 4/4 |
| Fase 2 — Webhooks y Notificaciones | ✅ 9/9 |
| Fase 3 — Deuda Técnica | ✅ 6/6 |
| **Total** | **✅ 31/31** |

Detalle de cada fase en [`docs/estado.md`](docs/estado.md) y plan de ejecución en [`docs/ejecucion.md`](docs/ejecucion.md).

---

## Documentación

- [Arquitectura](docs/arqui.md)
- [Plan de ejecución](docs/ejecucion.md)
- [Estado del proyecto](docs/estado.md)
- [Guía de deploy](docs/DEPLOY_UBUNTU.md)
- [Integración POS ↔ API](docs/integracion.md)
- [Guía de API Keys](docs/api-keys.md)
- [Setup de Celery](docs/CELERY_SETUP.md)
- [Setup de Sentry](docs/SENTRY_SETUP.md)
- [Setup de Staging](docs/STAGING_QUICK_SETUP.md)

---

## Licencia

Propietaria — DerejSoft. Todos los derechos reservados.
