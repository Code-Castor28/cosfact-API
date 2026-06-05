from rest_framework.routers import DefaultRouter
from .views import WebhookViewSet

app_name = "webhooks"

router = DefaultRouter()
router.register(r"webhooks", WebhookViewSet, basename="webhook")

urlpatterns = router.urls
