from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ApiKeyViewSet

app_name = "api_keys"

router = DefaultRouter()
router.register(r"", ApiKeyViewSet, basename="api-key")

urlpatterns = [
    path("", include(router.urls)),
]
