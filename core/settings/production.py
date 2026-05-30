import os
from .base import *

DEBUG = False

# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE HOSTS (ALLOWED_HOSTS)
# ------------------------------------------------------------------------------
# Lee el string del .env, lo divide por comas y limpia espacios de cada host
allowed_hosts_raw = os.getenv('ALLOWED_HOSTS', '').split(',')
ALLOWED_HOSTS = [
    host.strip() 
    for host in allowed_hosts_raw 
    if host.strip()
]
ALLOWED_HOSTS.append('testserver')

# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE ORÍGENES DE CONFIANZA CSRF
# ------------------------------------------------------------------------------
# Lee el string del .env, lo divide por comas y limpia espacios de cada origen
csrf_origins_raw = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
CSRF_TRUSTED_ORIGINS = [
    origin.strip() 
    for origin in csrf_origins_raw 
    if origin.strip()
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

# ─── HTTPS y cookies ──────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # para Nginx

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
        'level': 'WARNING',
    },
}
