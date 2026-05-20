from rest_framework.routers import DefaultRouter
from users.views import UsuarioViewSet
from empresas.views import EmpresaViewSet
from api_keys.views import ApiKeyViewSet
from sequences.views import SecuencialViewSet
from subscriptions.views import PlanViewSet, SuscripcionViewSet, PaqueteComprobantesViewSet
from pagos.views import PagoViewSet

# Router central para toda la API v1
router = DefaultRouter()

# Formato: router.register(r'prefijo-plural', ViewSet, basename='nombre-singular')
router.register(r'usuarios', UsuarioViewSet, basename='usuario')
router.register(r'empresas', EmpresaViewSet, basename='empresa')
router.register(r'api-keys', ApiKeyViewSet, basename='api-key')
router.register(r'secuenciales', SecuencialViewSet, basename='secuencial')
router.register(r'planes', PlanViewSet, basename='plan')
router.register(r'suscripciones', SuscripcionViewSet, basename='suscripcion')
router.register(r'paquetes', PaqueteComprobantesViewSet, basename='paquete')
router.register(r'pagos', PagoViewSet, basename='pago')
