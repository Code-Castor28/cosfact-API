import os
from .base import *


# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE HOSTS (ALLOWED_HOSTS)
# ------------------------------------------------------------------------------
import os as _os
_hosts_raw = _os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _hosts_raw.split(',') if h.strip()]
ALLOWED_HOSTS.append('testserver')

# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE ORÍGENES DE CONFIANZA CSRF
# ------------------------------------------------------------------------------
_origins_raw = _os.environ.get('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _origins_raw.split(',') if o.strip()]
ALLOWED_HOSTS.append('testserver')

# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE ORÍGENES DE CONFIANZA CSRF
# ------------------------------------------------------------------------------
_origins_value = env('CSRF_TRUSTED_ORIGINS')
_origins_str = str(_origins_value) if _origins_value else ''
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in _origins_str.split(',') if o.strip()
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
        'CONN_MAX_AGE': 60,        # conexiones persistentes
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# En producción DEBUG siempre es False
DEBUG = False

# ─── HTTPS y cookies ──────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Usar sesiones para guardar token CSRF (más confiable en este escenario)
CSRF_USE_SESSIONS = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # para Nginx

# Configurar dominios de cookies de forma flexible
# None permite que funcione con cualquier subdominio
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True  # Permitir almacenamiento en sesión
# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    "https://derejfact.com",
    "https://samboxderejfact.derejsoft.com",
    "https://derejpanel.derejsoft.com",
    "http://127.0.0.1:5500",
]
CORS_ALLOW_CREDENTIALS = True

# ─── Logs en producción (a archivo, no consola) ─────────────────────────────── Así obtienes una cadena y el type checker lo entiende
LOG_DIR = env.str('LOG_DIR', default=os.path.join(BASE_DIR, 'logs'))
os.makedirs(LOG_DIR, exist_ok=True)          # LOG_DIR es str
LOG_FILE = os.path.join(LOG_DIR, 'django.log')  # funciona

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
