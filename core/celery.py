import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')

app = Celery('derejfact')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat - Schedule de tareas periódicas
app.conf.beat_schedule = {
    'generar-pagos-automaticos': {
        'task': 'pagos.generar_pagos_automaticos',
        'schedule': crontab(hour=0, minute=0),  # Diariamente a las 00:00
        'options': {
            'queue': 'default',
            'expires': 3600,  # Expirar en 1 hora si no se ejecuta
        }
    },
    'notificar-pagos-proximos': {
        'task': 'pagos.notificar_pagos_proximos',
        'schedule': crontab(hour=8, minute=0),  # Diariamente a las 08:00
        'options': {
            'queue': 'default',
            'expires': 3600,
        }
    },
    'reintentar-contingencia': {
        'task': 'dgii.reintentar_contingencia',
        'schedule': crontab(hour=2, minute=0),  # 2:00 AM diario
        'options': {
            'queue': 'default',
            'expires': 3600,
        }
    },
    'alertar-balance-bajo': {
        'task': 'notificaciones.alertar_balance_bajo',
        'schedule': crontab(hour=6, minute=0),  # 6:00 AM diario
        'options': {
            'queue': 'default',
            'expires': 3600,
        }
    },
    'alertar-certificado-vencimiento': {
        'task': 'notificaciones.alertar_certificado_vencimiento',
        'schedule': crontab(hour=6, minute=30),  # 6:30 AM diario
        'options': {
            'queue': 'default',
            'expires': 3600,
        }
    },
}
