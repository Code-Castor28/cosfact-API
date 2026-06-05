from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SecuencialViewSet, onboarding

app_name = "sequences"

router = DefaultRouter()
router.register(r"secuenciales", SecuencialViewSet, basename="secuencial")

urlpatterns = [
    path("secuencias/", onboarding, name="onboarding"),
    path("", include(router.urls)),
]
