# Pago — App de Pagos Manuales

> Documento de contexto y plan de implementación para la app `pagos`.

---

## 1. Objetivo

App que permita registrar pagos manuales (sin pasarela) y actualizar el estado de las suscripciones.
Diseñada para integrar pasarelas de pago más adelante.

---

## 2. Reglas de Negocio

### 2.1 Requisitos para crear un pago
- La empresa **debe existir** y estar activa
- La empresa **debe tener un Plan** contratado
- La empresa **debe tener una Suscripción** (aunque esté VENCIDA o SUSPENDIDA)

### 2.2 Lógica de fecha_corte (período de pago)

Cada plan tiene un **día de corte fijo** por mes (ej: día 25).

| Situación | Período asignado |
|-----------|------------------|
| Pago ANTES o el día del corte | Mes actual |
| Pago DESPUÉS del corte | Mes siguiente |

**Ejemplo** con fecha_corte = 25:
- Pago el 20 de mayo → período = mayo 2026
- Pago el 28 de mayo → período = junio 2026

### 2.3 Validación de duplicados por período

No puede existir más de un pago confirmado por empresa en el mismo período (mes + año).
Si ya existe `HistorialPago` para ese período → error.

### 2.4 Suscripción (la misma, no se crea nueva)

Al confirmar un pago:
- La **misma suscripción** se actualiza (no se crea una nueva)
- `fecha_inicio` = primer día del período asignado
- `fecha_renovacion` = último día del período asignado
- `estado` = ACTIVA
- `plan` = plan del pago
- `ciclo` = MENSUAL o ANUAL

### 2.5 Paquete (nuevo cada período)

- Cada período se crea un **nuevo** `PaqueteComprobantes`
- `total_comprobantes` = plan.limite_comprobantes
- `estado` = ACTIVO
- Los comprobantes no consumidos del período anterior **no se acumulan** (se pierden)

### 2.6 Historial explícito por período

Cada pago confirmado crea un registro en `HistorialPago` con:
- Período (mes + año)
- Monto pagado
- Comprobantes asignados

---

## 3. Modelos

### 3.1 Pago

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | PK |
| `empresa` | FK → Empresa | Requerido |
| `suscripcion` | FK → Suscripcion | Requerido |
| `plan` | FK → Plan | Requerido |
| `monto` | Decimal | > 0 |
| `moneda` | String(10) | "DOP" o "USD" |
| `metodo_pago` | Choice | EFECTIVO, TRANSFERENCIA, DEPOSITO, CHEQUE, OTRO |
| `referencia` | String(100) | Número de referencia/boleta |
| `fecha_pago` | DateTime | Fecha en que se realizó el pago |
| `fecha_corte` | Integer | Día fijo del mes (1-28) |
| `observaciones` | Text | Notas opcionales |
| `estado` | Choice | PENDIENTE, CONFIRMADO, RECHAZADO |
| `confirmado_por` | FK → Usuario | Nullable |
| `fecha_confirmacion` | DateTime | Nullable |
| `creado_at` | DateTime | auto_now_add |
| `actualizado_at` | DateTime | auto_now |

### 3.2 HistorialPago

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | PK |
| `empresa` | FK → Empresa | |
| `suscripcion` | FK → Suscripcion | La misma suscripción, actualizada |
| `plan` | FK → Plan | Plan vigente en ese período |
| `pago` | FK → Pago | Pago que confirmó este período |
| `paquete` | FK → PaqueteComprobantes | Paquete creado para este período |
| `periodo_mes` | Integer | 1-12 |
| `periodo_ano` | Integer | Ej: 2026 |
| `monto_pagado` | Decimal | pago.monto |
| `comprobantes_asignados` | Integer | plan.limite_comprobantes |
| `creado_at` | DateTime | auto_now_add |

---

## 4. Endpoints API

### 4.1 CRUD Pagos

| Método | Ruta | Descripción | Permisos |
|--------|------|-------------|----------|
| GET | `/api/v1/pagos/` | Listar pagos | SUPERADMIN |
| POST | `/api/v1/pagos/` | Crear pago | SUPERADMIN |
| GET | `/api/v1/pagos/{id}/` | Ver detalle | SUPERADMIN |
| PATCH | `/api/v1/pagos/{id}/` | Actualizar | SUPERADMIN |
| DELETE | `/api/v1/pagos/{id}/` | Eliminar (solo PENDIENTE) | SUPERADMIN |

### 4.2 Acciones

| Método | Ruta | Descripción | Permisos |
|--------|------|-------------|----------|
| POST | `/api/v1/pagos/{id}/confirmar/` | Confirmar → activar suscripción + crear paquete + historial | SUPERADMIN |
| POST | `/api/v1/pagos/{id}/rechazar/` | Rechazar pago | SUPERADMIN |
| GET | `/api/v1/pagos/historial/` | Listar historial de pagos (filtrable por `?empresa=X`) | SUPERADMIN y API Key |

---

## 5. Flujo de Confirmación

```
1. Validar: pago.estado == PENDIENTE
2. Calcular período:
   - Si dia_actual <= fecha_corte → periodo = (mes_actual, año_actual)
   - Si dia_actual > fecha_corte → periodo = (mes_siguiente, año_siguiente si corresponde)
3. Validar: no existe HistorialPago para ese período + empresa → error si existe
4. Actualizar Pago:
   - estado = CONFIRMADO
   - confirmado_por = request.user
   - fecha_confirmacion = ahora
5. Actualizar Suscripción (misma instancia):
   - fecha_inicio = primer_día(periodo)
   - fecha_renovacion = último_día(periodo)
   - estado = ACTIVA
   - plan = pago.plan
6. Crear PaqueteComprobantes:
   - total_comprobantes = plan.limite_comprobantes
   - comprobantes_usados = 0
   - estado = ACTIVO
   - origen = SUSCRIPCION
   - suscripcion = suscripción actualizada
   - empresa = pago.empresa
   - plan = pago.plan
7. Crear HistorialPago:
   - periodo_mes, periodo_ano
   - pago = este pago
   - paquete = paquete creado
   - monto_pagado = pago.monto
   - comprobantes_asignados = plan.limite_comprobantes
8. Retornar: { pago, suscripcion, paquete, historial }
```

---

## 6. Integración Futura con Pasarelas

El modelo `Pago` está diseñado para extenderse:

```python
# Futuro:
tipo_pasarela = models.CharField(
    max_length=20,
    choices=[('STRIPE', 'Stripe'), ('PAYPAL', 'PayPal')],
    null=True, blank=True
)
datos_pasarela = models.JSONField(
    null=True, blank=True,
    help_text="Datos de la pasarela ej: stripe_payment_intent_id"
)
```

---

## 7. Dependencias

- App `pagos` depende de: `empresas`, `subscriptions`, `users`
- `subscriptions` **no** depende de `pagos` (se mantiene independiente)

---

## 8. Estructura de Archivos

```
apps/pagos/
├── __init__.py
├── apps.py
├── models.py
├── serializers.py
├── views.py
├── permissions.py
├── urls.py
├── admin.py
├── tests.py
└── migrations/
    └── 0001_initial.py
```

---

## 9. Cambios en core/settings/base.py

- Agregar `'pagos'` a `INSTALLED_APPS`

## 10. Cambios en core/urls.py

- Agregar: `path('api/v1/pagos/', include('pagos.urls', namespace='pagos'))`

---

## 11. Validaciones en `apps/subscriptions/models.py`

Se agregarán validaciones en el método `clean()` del modelo `PaqueteComprobantes` para blindar la lógica de negocio:

### 11.1 Validación de límite de comprobantes

```
total_comprobantes ≤ plan.limite_comprobantes
```

Si el plan es "Básico" con 10 comprobantes, el paquete NO puede tener `total_comprobantes = 20`.

### 11.2 Validación de fecha_vencimiento según ciclo

```
si suscripcion.ciclo == MENSUAL:
    fecha_vencimiento ≤ fecha_inicio + 1 mes

si suscripcion.ciclo == ANUAL:
    fecha_vencimiento ≤ fecha_inicio + 1 año
```

### 11.3 Responsabilidad

- **La vista de pagos** calcula y pasa la `fecha_vencimiento` al crear el paquete
- **El modelo** solo valida que no exceda el límite permitido según el ciclo

### 11.4 Código de ejemplo del método clean()

```python
def clean(self):
    if self.plan and self.total_comprobantes > self.plan.limite_comprobantes:
        raise ValidationError({
            "total_comprobantes": (
                f"El plan '{self.plan.nombre}' solo permite "
                f"{self.plan.limite_comprobantes} comprobantes."
            )
        })
    
    if self.suscripcion and self.fecha_vencimiento:
        from dateutil.relativedelta import relativedelta
        fecha_inicio = self.suscripcion.fecha_inicio or timezone.now().date()
        ciclo = self.suscripcion.ciclo
        
        if ciclo == Suscripcion.CICLO_MENSUAL:
            max_fecha = fecha_inicio + relativedelta(months=1)
            if self.fecha_vencimiento.date() > max_fecha:
                raise ValidationError({
                    "fecha_vencimiento": (
                        f"Ciclo MENSUAL. La fecha de vencimiento no puede "
                        f"exceder 1 mes ({max_fecha})."
                    )
                })
        elif ciclo == Suscripcion.CICLO_ANUAL:
            max_fecha = fecha_inicio + relativedelta(years=1)
            if self.fecha_vencimiento.date() > max_fecha:
                raise ValidationError({
                    "fecha_vencimiento": (
                        f"Ciclo ANUAL. La fecha de vencimiento no puede "
                        f"exceder 1 año ({max_fecha})."
                    )
                })
```

---

## 12. Tiempo de Gracia (Implementación Requerida en App Suscripciones)

### 12.1 Campo en Plan

Agregar campo `dias_gracia` al modelo `Plan`:

```python
dias_gracia = models.PositiveSmallIntegerField(
    default=0,
    validators=[MaxValueValidator(15)],
    help_text="Días de gracia después de la fecha de renovación (0-15)."
)
```

### 12.2 Reglas de Negocio

| Situación | Comportamiento |
|-----------|----------------|
| Empresa paga ANTES o el día de `fecha_renovacion` | Sin tiempo de gracia, proceso normal |
| Empresa NO paga en `fecha_renovacion` | Entra en tiempo de gracia si el Plan lo tiene configurado |
| Durante tiempo de gracia | Puede seguir emitiendo comprobantes |
| Fin del tiempo de gracia | Se bloquea la emisión |

**Fórmula de verificación:**
```
fecha_limite = suscripcion.fecha_renovacion + dias_gracia (del Plan)
si hoy <= fecha_limite → puede emitir
si hoy > fecha_limite → bloqueado
```

### 12.3 Implementación en Suscripcion

Modificar property `esta_activa`:

```python
from django.utils import timezone
from datetime import timedelta

@property
def esta_activa(self):
    if self.estado != self.ESTADO_ACTIVA:
        return False
    
    fecha_renovacion = self.fecha_renovacion
    if fecha_renovacion >= timezone.now().date():
        return True
    
    dias_gracia = getattr(self.plan, 'dias_gracia', 0) or 0
    if dias_gracia == 0:
        return False
    
    fecha_limite_gracia = fecha_renovacion + timedelta(days=dias_gracia)
    return timezone.now().date() <= fecha_limite_gracia
```

### 12.4 Implementación en PaqueteComprobantes

Modificar property `disponible`:

```python
@property
def disponible(self):
    if self.estado != self.ESTADO_ACTIVO:
        return False
    
    if self.fecha_vencimiento and timezone.now() > self.fecha_vencimiento:
        dias_gracia = 0
        if self.suscripcion:
            dias_gracia = getattr(self.suscripcion.plan, 'dias_gracia', 0) or 0
            if dias_gracia > 0:
                fecha_limite = self.fecha_vencimiento + timedelta(days=dias_gracia)
                if timezone.now() > fecha_limite:
                    return False
            else:
                return False
        else:
            return False
    
    return self.comprobantes_restantes > 0
```

### 12.5 Validaciones en PaqueteComprobantes.clean()

Según sección 11 del documento:

```python
def clean(self):
    # 12.5.1 Validación de límite de comprobantes
    if self.plan and self.total_comprobantes > self.plan.limite_comprobantes:
        raise ValidationError({
            "total_comprobantes": (
                f"El plan '{self.plan.nombre}' solo permite "
                f"{self.plan.limite_comprobantes} comprobantes."
            )
        })
    
    # 12.5.2 Validación de fecha_vencimiento según ciclo
    if self.suscripcion and self.fecha_vencimiento:
        from dateutil.relativedelta import relativedelta
        fecha_inicio = self.suscripcion.fecha_inicio or timezone.now().date()
        ciclo = self.suscripcion.ciclo
        
        if ciclo == Suscripcion.CICLO_MENSUAL:
            max_fecha = fecha_inicio + relativedelta(months=1)
            if self.fecha_vencimiento.date() > max_fecha:
                raise ValidationError({
                    "fecha_vencimiento": (
                        f"Ciclo MENSUAL. La fecha de vencimiento no puede "
                        f"exceder 1 mes ({max_fecha})."
                    )
                })
        elif ciclo == Suscripcion.CICLO_ANUAL:
            max_fecha = fecha_inicio + relativedelta(years=1)
            if self.fecha_vencimiento.date() > max_fecha:
                raise ValidationError({
                    "fecha_vencimiento": (
                        f"Ciclo ANUAL. La fecha de vencimiento no puede "
                        f"exceder 1 año ({max_fecha})."
                    )
                })
```

### 12.6 Serializers

Agregar `dias_gracia` a:
- `PlanSerializer` (lectura/escritura)
- `SuscripcionSerializer` (solo lectura)

---

*Última actualización: Mayo 2026*
