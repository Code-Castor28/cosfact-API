# apps/empresas/api_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import EmpresaViewSet

app_name = 'empresas_api'

router = DefaultRouter()
router.register(r'', EmpresaViewSet, basename='empresa')

urlpatterns = [
    path('', include(router.urls)),
]
