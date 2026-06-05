# Implementación: Refactorización de Rutas API (URLs)

Resumen
-------
Documento técnico con el plan de implementación para refactorizar las rutas REST del proyecto.
Objetivo: eliminar registros de router vacíos, usar prefijos semánticos, mover endpoints relacionados dentro de ViewSets con `@action` cuando corresponda y dejar una arquitectura compatible con nested routers, versionado y OpenAPI.

Objetivos técnicos
------------------
- Prefijos semánticos y explícitos por recurso (no usar router.register(r"", ...)).
- Mantener/añadir `@action(detail=True|False)` para operaciones especiales.
- Evitar rutas sueltas fuera del recurso principal cuando pertenezcan al mismo dominio.
- Compatibilidad con nested routers, versionado (/api/v1/...), OpenAPI, permisos por endpoint, throttling y testing.

Diagnóstico rápido (estado actual)
----------------------------------
- Varias apps usan `router.register(r"", ...)` (empresas, users, api_keys, sequences, pagos). Esto genera rutas implícitas sin prefijo y dificulta el mantenimiento.
- Algunas apps mezclan rutas manuales con router (ej. `historial/` en pagos) en lugar de usar `@action`.
- `subscriptions` ya está correctamente prefijado (buen ejemplo).

Propuesta de estructura (resumen)
---------------------------------
- Centralizar el enrutamiento de la API en un módulo raíz (recomendado: `core/api_router.py`).
- Registrar cada ViewSet con un prefijo semántico y plural (ej. `router.register(r'pagos', PagoViewSet)`).
- Operaciones relacionadas:
  - @action(detail=True) → cuando la operación es sobre una instancia (confirmar/rechazar pago).
  - @action(detail=False) → cuando es una operación de colección (historial filtrable).
- Mantener o crear ViewSet independientes solo si el recurso tiene ciclo de vida propio y CRUD completo.

Endpoints resultantes (propuesta, /api/v1/)
-----------------------------------------
- Auth
  - POST /api/v1/auth/login/
  - POST /api/v1/auth/token/refresh/
  - POST /api/v1/auth/recover-password/

- Usuarios
  - GET/POST /api/v1/usuarios/
  - GET/PATCH/DELETE /api/v1/usuarios/{id}/
  - GET/PUT/PATCH /api/v1/usuarios/me/  (@action(detail=False))
  - POST /api/v1/usuarios/me/change-password/ (@action(detail=False))

- Empresas
  - GET/POST /api/v1/empresas/
  - GET/PATCH /api/v1/empresas/{id}/
  - GET /api/v1/empresas/{id}/suscripcion/ (@action(detail=True))
  - GET /api/v1/empresas/{id}/comprobantes/ (@action(detail=True))

- Subscriptions (ya semánticas)
  - GET/POST /api/v1/planes/
  - GET/POST /api/v1/suscripciones/
  - GET/POST /api/v1/paquetes/

- Secuenciales
  - GET/POST /api/v1/secuenciales/
  - GET/PATCH /api/v1/secuenciales/{id}/
  - GET /api/v1/secuenciales/{id}/preview/ (@action)
  - POST /api/v1/secuenciales/{id}/bloquear/ (@action)
  - POST /api/v1/secuenciales/{id}/desbloquear/ (@action)

- Pagos
  - GET/POST /api/v1/pagos/
  - GET/PATCH/DELETE /api/v1/pagos/{id}/
  - POST /api/v1/pagos/{id}/confirmar/ (@action(detail=True))
  - POST /api/v1/pagos/{id}/rechazar/ (@action(detail=True))
  - GET /api/v1/pagos/historial/ (@action(detail=False) en PagoViewSet) — listado filtrable de HistorialPago

- Api Keys
  - GET/POST /api/v1/api-keys/
  - POST /api/v1/api-keys/{id}/revocar/ (@action)
  - POST /api/v1/api-keys/{id}/rotar/ (@action)

Decisiones clave y reglas
-------------------------
- Prefijo: usar sustantivos en plural (`/pagos/`, `/empresas/`), consistentemente.
- @action(detail=True) para comportamientos sobre recursos individuales.
- @action(detail=False) para consultas/operaciones sobre colecciones.
- Crear ViewSet separado solo si el recurso necesita CRUD independiente y permisos/limites específicos.
- Mantener get_permissions() en ViewSets con branching por `self.action` (permite granularidad).

Implementación paso a paso
--------------------------
1) Branching: crear rama `feature/urls-refactor`.
2) Añadir `core/api_router.py` y registrar los ViewSets con nombres semánticos.
   - No borrar rutas existentes aún: exponer ambos conjuntos en paralelo para pruebas.
3) Mover endpoints sueltos dentro de sus ViewSets como `@action` (ej. historial → PagoViewSet.historial).
4) Actualizar los `app/urls.py` para usar prefijos explícitos o dejarlos vacíos si centralizamos en `core/api_router.py`.
5) Tests: escribir tests de integración para nuevos endpoints, mantener tests que verifiquen compatibilidad.
6) Swap: una vez verificado, eliminar los `router.register(r"", ...)` y cleanup de includes duplicados.
7) Documentación: actualizar OpenAPI/Swagger y `docs/contexto_pago.md` y esta `docs/imple.md`.

Pruebas y CI
------------
- Escribir tests de contrato (smoke) que validen: list, retrieve y acciones críticas (confirmar_pago, revocar_api_key).
- Añadir job CI que haga:
  - pytest (unit + integration)
  - generación de OpenAPI y verificación básica
  - grep que confirme que no hay `router.register(r"",` en master (policy check)

Riesgos y mitigaciones
----------------------
- Ruptura de clientes: Mitigar exponiendo rutas nuevas en paralelo y publicando deprecación en Swagger; plan de eliminación en próxima versión mayor.
- Gaps de seguridad al mover permisos: usar tests de autorización y revisar `get_permissions()` por action.
- Bugs en nested routers: testear casos nested en staging antes de producción.

Ejemplos de código (fragmentos)
-------------------------------

core/api_router.py (ejemplo)
```python
from rest_framework.routers import DefaultRouter
from users.views import UsuarioViewSet
from empresas.views import EmpresaViewSet
from api_keys.views import ApiKeyViewSet
from sequences.views import SecuencialViewSet
from subscriptions.views import PlanViewSet, SuscripcionViewSet, PaqueteComprobantesViewSet
from pagos.views import PagoViewSet

router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet, basename='usuario')
router.register(r'empresas', EmpresaViewSet, basename='empresa')
router.register(r'api-keys', ApiKeyViewSet, basename='api-key')
router.register(r'secuenciales', SecuencialViewSet, basename='secuencial')
router.register(r'planes', PlanViewSet, basename='plan')
router.register(r'suscripciones', SuscripcionViewSet, basename='suscripcion')
router.register(r'paquetes', PaqueteComprobantesViewSet, basename='paquete')
router.register(r'pagos', PagoViewSet, basename='pago')

# En core/urls.py incluir: path('api/v1/', include(router.urls))
```

PagoViewSet.historial (ejemplo)
```python
from rest_framework.decorators import action
from rest_framework.response import Response

class PagoViewSet(viewsets.ModelViewSet):
    ...
    @action(detail=False, methods=['get'], url_path='historial')
    def historial(self, request):
        qs = HistorialPago.objects.all().order_by('-periodo_ano','-periodo_mes')
        empresa = request.query_params.get('empresa')
        if empresa:
            qs = qs.filter(empresa_id=empresa)
        page = self.paginate_queryset(qs)
        serializer = HistorialPagoSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)
```

Plan de despliegue y compatibilidad
-----------------------------------
- Fase 1 (staging): exponer rutas nuevas en paralelo.
- Fase 2 (canary): redirigir clientes internos a rutas nuevas y ejecutar tests.
- Fase 3 (prod): desactivar rutas antiguas y eliminar código en release mayor; publicar changelog y notas de deprecación.

Recomendaciones enterprise
--------------------------
- Mantener convención plural para recursos y `api/v{n}` en URI.
- Centralizar registro de rutas y prohibir `router.register(r"", ...)` por regla del repositorio (CI check).
- Adoptar drf-nested-routers si las relaciones anidadas son frecuentes.
- Crear contrato API y tests de integración para consumidores externos.

Conclusión
----------
El refactor mejora la mantenibilidad, descubribilidad y escalabilidad de la API. La estrategia propuesta permite una transición segura (exponer rutas nuevas en paralelo), mantiene la granularidad de permisos y deja la arquitectura lista para nested routers y documentación automática.

---
Última actualización: {fecha}
