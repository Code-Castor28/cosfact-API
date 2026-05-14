from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SecuencialViewSet

app_name = "sequences"

router = DefaultRouter()
router.register(r"", SecuencialViewSet, basename="secuencial")

urlpatterns = [
    path("", include(router.urls)),
]
