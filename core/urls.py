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
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('users:login'), name='home'),
    path('', include('users.urls')),

    # --- API ---
    path('api/v1/users/', include('users.api_urls', namespace='users_api')),
    path('api/v1/empresas/', include('empresas.api_urls', namespace='empresas_api')),
    path('api/v1/api-keys/', include('api_keys.urls', namespace='api_keys')),
    path('api/v1/subscriptions/',
         include('subscriptions.urls', namespace='subscriptions')),
    path('api/v1/sequences/', include('sequences.urls', namespace='sequences')),
]
# Solo en desarrollo: permitir que Django sirva archivos media y static
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
