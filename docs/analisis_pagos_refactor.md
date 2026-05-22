# Análisis y Refactor - App de Pagos

> Documento que detalla los problemas encontrados en la app `pagos` y la propuesta de mejora basada en requisitos del usuario.

**Fecha**: 21 de mayo de 2026  
**Versión**: 1.0  
**Estado**: Análisis completado - Listo para implementación

---

## 1. Contexto Definido por Usuario

### 1.1 Flujo Objetivo

1. **Generación Automática**: Pagos se crean 15 días antes de vencimiento de suscripción
2. **Estados Válidos**: Para todas las suscripciones excepto CANCELADAS
3. **Monto**: Viene del plan (NO editable)
4. **API GET**: Lista pagos PENDIENTES con monto READ-ONLY
5. **Confirmación**: Usuario actualiza SOLO `metodo_pago` + `referencia`
6. **Post-Confirmación**: Valida duplicados por período → crea historial → actualiza suscripción
7. **Regla Crítica**: Nunca pago adelantado si hay otro pendiente del mismo cliente

### 1.2 Requisitos Especiales

- **Adelantos**: Solo si se generan manualmente y no hay otros pendientes
- **Cambios de Plan**: Pueden generar pagos especiales
- **Comprobantes**: Métodos no-EFECTIVO requieren `referencia`/número para rastreo
- **Permisos**: Solo SUPERADMIN
- **Tiempo Previo**: 15 días antes del vencimiento de suscripción
- **Validación de Comprobantes**: Ambos (verifica comprobante + confía en empresa)

---

## 2. Problemas en Código Actual

| # | Problema | Ubicación | Severidad | Impacto |
|---|----------|-----------|-----------|---------|
| 1 | **Sin generación automática** | Falta celery task | 🔴 CRÍTICA | Pagos nunca se crean → usuarios no saben qué deben pagar |
| 2 | **Monto editable** | `PagoSerializer.fields` | 🔴 CRÍTICA | Riesgo: alguien modifica cantidad adeudada |
| 3 | **Flujo confuso** | Views (POST vs PATCH) | 🟠 ALTA | POST crea pago, PATCH actualiza → no es claro cuál confirma |
| 4 | **Sin validación de adelantos** | `perform_create` | 🟠 ALTA | Permite múltiples pagos pendientes simultáneamente |
| 5 | **Referencia no obligatoria** | Modelo y Serializer | 🟠 ALTA | Transferencias/cheques sin número de rastreo |
| 6 | **Plan editable** | `PagoSerializer.fields` | 🟡 MEDIA | Debería venir de la suscripción (no editable) |
| 7 | **Empresa editable** | `PagoSerializer.fields` | 🟡 MEDIA | Debería venir de la suscripción (no editable) |

---

## 3. Propuesta de Cambios

### 3.1 Serializer (apps/pagos/serializers.py)

**Cambios a PagoSerializer:**

```python
# NUEVO: PagoUpdateSerializer para confirmar pago
class PagoUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer SOLO para actualizar método de pago y referencia.
    Todos los otros campos son read-only.
    """
    class Meta:
        model = Pago
        fields = [
            "id",
            "metodo_pago",
            "referencia",
            "observaciones",  # optional
            "estado",  # readonly, cambiar cuando confirma
        ]
        read_only_fields = [
            "id",
            "estado",
        ]
    
    def validate(self, data):
        """
        Si metodo_pago != EFECTIVO, referencia es requerida.
        """
        metodo = data.get('metodo_pago')
        referencia = data.get('referencia', '').strip()
        
        if metodo and metodo != Pago.METODO_EFECTIVO:
            if not referencia:
                raise serializers.ValidationError({
                    "referencia": f"Requerida para pagos por {metodo}"
                })
        
        return data


# MODIFICAR: PagoSerializer (GET list)
class PagoSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    plan_nombre = serializers.CharField(source="plan.nombre", read_only=True)
    
    class Meta:
        model = Pago
        fields = [
            "id",
            "empresa",
            "empresa_nombre",
            "suscripcion",
            "plan",
            "plan_nombre",
            "monto",
            "moneda",
            "metodo_pago",
            "referencia",
            "fecha_pago",
            "fecha_corte",
            "observaciones",
            "estado",
            "confirmado_por",
            "fecha_confirmacion",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = [
            "id",
            "monto",        # ← NUEVO: read-only
            "moneda",       # ← NUEVO: read-only
            "plan",         # ← NUEVO: read-only
            "empresa",      # ← NUEVO: read-only
            "suscripcion",  # ← NUEVO: read-only
            "fecha_pago",   # ← NUEVO: read-only
            "fecha_corte",  # ← NUEVO: read-only
            "estado",
            "confirmado_por",
            "fecha_confirmacion",
            "creado_at",
            "actualizado_at",
        ]
```

---

### 3.2 Views (apps/pagos/views.py)

**Cambios a PagoViewSet:**

```python
class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.select_related(
        "empresa", "plan", "suscripcion", "confirmado_por"
    ).all()
    permission_classes = [IsSuperAdmin]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PagoDetailSerializer
        if self.action == 'actualizar_confirmacion':  # ← NUEVO
            return PagoUpdateSerializer
        if self.action == 'historial':
            return HistorialPagoSerializer
        return PagoSerializer

    def get_queryset(self):
        """
        Por defecto, retorna solo pagos PENDIENTES.
        Query param: ?estado=CONFIRMADO para filtrar otros.
        """
        queryset = super().get_queryset()
        estado = self.request.query_params.get('estado')
        
        if not estado:
            # Por defecto: solo PENDIENTES
            queryset = queryset.filter(estado=Pago.ESTADO_PENDIENTE)
        else:
            queryset = queryset.filter(estado=estado)
        
        return queryset

    def create(self, request, *args, **kwargs):
        """
        POST deshabilitado para usuario normal.
        Solo para casos especiales: adelantos, cambios de plan.
        Requiere validación adicional.
        """
        return Response(
            {
                "error": "No se puede crear pagos directamente. "
                         "Los pagos se generan automáticamente. "
                         "Contacta a administración para casos especiales."
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    @action(detail=True, methods=['patch'])
    def actualizar_confirmacion(self, request, pk=None):
        """
        PATCH /api/v1/pagos/{id}/actualizar_confirmacion/
        
        Permite actualizar SOLO:
        - metodo_pago
        - referencia
        - observaciones
        
        Al completar estos campos, confirma el pago automáticamente.
        """
        pago = self.get_object()

        # Validar estado
        if pago.estado != Pago.ESTADO_PENDIENTE:
            return Response(
                {
                    "error": f"No se puede actualizar pago en estado {pago.estado}. "
                             "Solo PENDIENTE."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar referencia si no es EFECTIVO
        metodo_pago = request.data.get('metodo_pago', pago.metodo_pago)
        referencia = request.data.get('referencia', '').strip()

        if metodo_pago and metodo_pago != Pago.METODO_EFECTIVO:
            if not referencia:
                return Response(
                    {
                        "error": f"Referencia requerida para pagos por {metodo_pago}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Usar serializer de actualización
        serializer = self.get_serializer(pago, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Aquí NO guardamos aún, primero confirmamos
        pago.metodo_pago = serializer.validated_data.get(
            'metodo_pago', 
            pago.metodo_pago
        )
        pago.referencia = serializer.validated_data.get(
            'referencia', 
            pago.referencia
        )
        pago.observaciones = serializer.validated_data.get(
            'observaciones', 
            pago.observaciones
        )
        pago.save()

        # Automáticamente confirmar pago (llamar a confirmar)
        return self._confirmar_pago_internamente(pago, request)

    def _confirmar_pago_internamente(self, pago, request):
        """
        Lógica de confirmación interna (reutilizable).
        Equivalente a la action 'confirmar' actual, pero sin requerer
        un POST adicional.
        """
        # TODO: Copiar lógica de confirmar() aquí
        # Incluye: validación de período, creación de HistorialPago, etc.
        pass

    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        """
        [DEPRECATED - usar actualizar_confirmacion en su lugar]
        
        Se mantiene por compatibilidad, pero en futuro será removido.
        """
        pago = self.get_object()
        # ... código actual ...

    def destroy(self, request, *args, **kwargs):
        """
        Solo se pueden eliminar pagos en estado PENDIENTE.
        """
        instance = self.get_object()
        if instance.estado != Pago.ESTADO_PENDIENTE:
            return Response(
                {"error": "Solo se pueden eliminar pagos en estado PENDIENTE."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)
```

---

### 3.3 Models (apps/pagos/models.py)

**Agregar validación en clean():**

```python
class Pago(models.Model):
    # ... campos existentes ...

    def clean(self):
        """
        Validaciones personalizadas:
        1. Si metodo_pago != EFECTIVO, referencia es requerida
        2. No puede haber otro pago PENDIENTE para el mismo cliente/período
        """
        super().clean()

        # Validación 1: Referencia
        if (self.metodo_pago and 
            self.metodo_pago != self.METODO_EFECTIVO and 
            not self.referencia.strip()):
            raise ValidationError({
                'referencia': f'Requerida para pagos por {self.metodo_pago}'
            })

        # Validación 2: No adelantos
        if self.estado == self.ESTADO_PENDIENTE and self.pk is None:  # Al crear
            existe_pendiente = Pago.objects.filter(
                empresa=self.empresa,
                estado=self.ESTADO_PENDIENTE,
            ).exclude(pk=self.pk).exists()

            if existe_pendiente:
                raise ValidationError({
                    'empresa': 'Ya existe un pago PENDIENTE para esta empresa. '
                               'No se permiten adelantos.'
                })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
```

---

### 3.4 Celery Task (apps/pagos/tasks.py) - NUEVA

**Crear archivo con task automática:**

```python
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from .models import Pago
from subscriptions.models import Suscripcion


@shared_task(name='pagos.generar_pagos_automaticos')
def generar_pagos_automaticos():
    """
    Crea Pago PENDIENTE para suscripciones que vencen en ~15 días.
    
    Lógica:
    - Busca: Suscripciones con estado != CANCELADA
    - Filtra: fecha_renovacion <= HOY + 15 días Y >= HOY
    - Valida: No exista otro Pago PENDIENTE del mismo período
    - Crea: Pago(estado=PENDIENTE, monto=plan.precio, metodo_pago=NULL)
    
    Se ejecuta: Diariamente (vía celery beat)
    """
    ahora = timezone.now()
    fecha_limite = ahora + timedelta(days=15)

    suscripciones = Suscripcion.objects.filter(
        estado__in=[
            Suscripcion.ESTADO_ACTIVA,
            Suscripcion.ESTADO_VENCIDA,
            Suscripcion.ESTADO_SUSPENDIDA,
        ],
        fecha_renovacion__lte=fecha_limite,
        fecha_renovacion__gte=ahora,
    ).select_related('empresa', 'plan')

    pagos_creados = 0

    for suscripcion in suscripciones:
        # Validar: no existe pago PENDIENTE ya
        existe_pendiente = Pago.objects.filter(
            empresa=suscripcion.empresa,
            estado=Pago.ESTADO_PENDIENTE,
        ).exists()

        if existe_pendiente:
            continue  # Ya hay pago pendiente, saltar

        # Calcular período
        fecha_pago = ahora
        fecha_corte = suscripcion.plan.fecha_corte if hasattr(suscripcion.plan, 'fecha_corte') else 1
        
        if fecha_pago.day <= fecha_corte:
            periodo_mes = fecha_pago.month
            periodo_ano = fecha_pago.year
        else:
            siguiente = fecha_pago + timedelta(days=30)
            periodo_mes = siguiente.month
            periodo_ano = siguiente.year

        # Validar: no existe HistorialPago para ese período
        from .models import HistorialPago
        existe_historial = HistorialPago.objects.filter(
            empresa=suscripcion.empresa,
            periodo_mes=periodo_mes,
            periodo_ano=periodo_ano,
        ).exists()

        if existe_historial:
            continue  # Ya pagó ese mes, saltar

        # Crear Pago
        try:
            with transaction.atomic():
                pago = Pago.objects.create(
                    empresa=suscripcion.empresa,
                    suscripcion=suscripcion,
                    plan=suscripcion.plan,
                    monto=suscripcion.plan.precio,  # Asume que el plan tiene precio
                    moneda=Pago.MONEDA_DOP,  # O del plan
                    metodo_pago='',  # Vacío, se rellenará al confirmar
                    referencia='',
                    fecha_pago=ahora,
                    fecha_corte=fecha_corte,
                    estado=Pago.ESTADO_PENDIENTE,
                )
                pagos_creados += 1
        except Exception as e:
            # Log error pero continuar
            print(f"Error creando pago para {suscripcion.empresa.rnc}: {e}")
            continue

    return {
        "status": "success",
        "pagos_creados": pagos_creados,
    }
```

---

### 3.5 Celery Beat Config (core/celery.py)

**Agregar schedule para task automática:**

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    # ... otras tasks ...
    'generar-pagos-automaticos': {
        'task': 'pagos.generar_pagos_automaticos',
        'schedule': crontab(hour=0, minute=0),  # Diariamente a las 00:00
    },
}
```

---

## 4. Flujo New (Diagrama)

```
┌─────────────────────────────────────────────────────────────┐
│                  SISTEMA AUTOMÁTICO (00:00 diario)           │
├─────────────────────────────────────────────────────────────┤
│ 1. Busca suscripciones con vencimiento en 15 días            │
│ 2. Valida: no hay Pago PENDIENTE ni HistorialPago existente  │
│ 3. Crea Pago(estado=PENDIENTE, monto=plan.precio)           │
│ 4. Notifica cliente (futuro)                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              USUARIO - DÍA X (cuando decide pagar)           │
├─────────────────────────────────────────────────────────────┤
│ GET /api/v1/pagos/                                           │
│  └─ Retorna: lista de PENDIENTES con monto READ-ONLY         │
│                                                               │
│ PATCH /api/v1/pagos/{id}/actualizar_confirmacion/            │
│  ├─ Body: {                                                   │
│  │   "metodo_pago": "TRANSFERENCIA",                         │
│  │   "referencia": "TRF-ABC123"                              │
│  │ }                                                          │
│  └─ Valida: referencia si metodo != EFECTIVO                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   SISTEMA - CONFIRMA PAGO                    │
├─────────────────────────────────────────────────────────────┤
│ 1. Calcula período (fecha_corte lógic)                       │
│ 2. Valida: no existe otro HistorialPago del período          │
│ 3. Actualiza Pago(estado=CONFIRMADO, confirmado_por=user)    │
│ 4. Crea HistorialPago                                        │
│ 5. Crea PaqueteComprobantes                                  │
│ 6. Actualiza Suscripción(estado=ACTIVA, fecha_inicio/fecha)  │
│ 7. Retorna: { pago, historial, paquete }                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Endpoints API (Nuevos)

| Método | Ruta | Descripción | Body | Retorna |
|--------|------|-------------|------|---------|
| GET | `/api/v1/pagos/` | Listar PENDIENTES | - | `[ { id, empresa, monto, metodo_pago, ... } ]` |
| GET | `/api/v1/pagos/?estado=CONFIRMADO` | Listar confirmados | - | `[ ... ]` |
| GET | `/api/v1/pagos/{id}/` | Ver detalle | - | `{ id, empresa, monto, ... }` |
| **PATCH** | `/api/v1/pagos/{id}/actualizar_confirmacion/` | **Confirmar pago** | `{ metodo_pago, referencia }` | `{ pago, historial, paquete }` |
| DELETE | `/api/v1/pagos/{id}/` | Eliminar (solo PENDIENTE) | - | `204 No Content` |

---

## 6. Cambios en Documentación Existente

**Actualizar** [docs/contexto_pago.md](contexto_pago.md):

- Remover sección sobre POST create (solo admins/especiales)
- Agregar sección sobre generación automática
- Documentar nuevo endpoint `actualizar_confirmacion`
- Aclarar validación de referencias
- Mostrar ejemplo de flow con curl/Postman

---

## 7. Checklist de Implementación

- [ ] Modificar `PagoSerializer` (make monto, plan, empresa read-only)
- [ ] Crear `PagoUpdateSerializer` (para confirmar)
- [ ] Refactor views: deshabilitar POST, agregar action `actualizar_confirmacion`
- [ ] Agregar validación `clean()` en modelo Pago
- [ ] Crear `apps/pagos/tasks.py` con task automática
- [ ] Configurar Celery Beat en `core/celery.py`
- [ ] Crear migration (si aplica)
- [ ] Actualizar documentación en `/docs/`
- [ ] Pruebas unitarias: validación de referencias
- [ ] Pruebas unitarias: generación automática
- [ ] Pruebas E2E: flujo completo

---

## 8. Notas Adicionales

### Consideraciones Futuras
- Integración con pasarelas de pago
- Webhook para confirmaciones automáticas
- Notificaciones por email/SMS
- Dashboard de monitoreo de pagos

### Seguridad
- Validar permisos: Solo SUPERADMIN accede a esta app
- Auditoría: `confirmado_por` y `fecha_confirmacion` se registran
- Rastreo: `referencia` obligatoria para métodos trazables

### Performance
- Índices en `(empresa, estado)` y `(estado, creado_at)` ya existen ✓
- Prefetch related para queries: `select_related` en ViewSet ✓
- Considerar caché para listados de PENDIENTES

