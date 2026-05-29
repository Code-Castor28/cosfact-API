"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import path, include
from core.views import health_check
from .api_router import router
import sentry_sdk
# ─── Debug: Sentry error testing ──────────────────────────────────────────────


def trigger_sentry_error(request: HttpRequest) -> HttpResponse:
    """Trigger a test error to verify Sentry is working.

            Usage: http://localhost:8000/sentry-debug/
            """
    raise ZeroDivisionError("Intentional error for testing")
    return HttpResponse(status=500)


urlpatterns = [
    path('admin/', admin.site.urls),

    # 2. AÑADE ESTA LÍNEA AL PRINCIPIO
    path('api/v1/health/', health_check, name='health_check'),

    # # --- Debug ---
    # path('sentry-debug/', trigger_sentry_error) if settings.DEBUG else None,

    # --- API Router Central ---
    path('api/v1/', include(router.urls)),

    # --- Auth (separado por claridad) ---
    path('api/v1/auth/', include('users.auth_urls')),

    # --- Inclusión legacy (compatible con apps que expongan rutas extras) ---
    path('api/v1/', include('dgii.urls')),
    path('api/v1/', include('webhooks.urls')),
    path('api/v1/', include('audit.urls')),
    path('api/v1/', include('comprobantes.urls')),
]
# Limpiar None values si DEBUG=False
urlpatterns = [url for url in urlpatterns if url is not None]

# Solo en desarrollo: permitir que Django sirva archivos media y static
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    urlpatterns.append(path('sentry-debug/', trigger_sentry_error))
