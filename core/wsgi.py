"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from django.core.wsgi import get_wsgi_application


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.production')

application = get_wsgi_application()

# Sentry init DESPUÉS de que Django está completamente configurado
from django.conf import settings  # noqa: E402

if getattr(settings, 'SENTRY_DSN', None):
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        traces_sample_rate=0.1,
        send_default_pii=True,
        environment=getattr(settings, 'ENVIRONMENT', 'production'),
        release=getattr(settings, 'APP_VERSION', 'unknown'),
    )
