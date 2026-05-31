# Plan de Mejora — App Pagos

## Problemas Identificados

1. **Bug del ciclo anual**: `_confirmar_pago_internamente()` siempre suma 1 mes, ignora `suscripcion.ciclo`.
2. **Bug del día 1**: Fuerza `fecha_inicio` al día 1 del mes y `fecha_renovacion` al último día.
3. **Campo fantasma `fecha_corte`**: Código referencia `pago.fecha_corte` y `plan.fecha_corte` pero ningún modelo lo declara. Columna existe en BD pero no en el modelo Python.
4. **POST deshabilitado**: `create()` retorna 405, impidiendo pagos manuales del SuperAdmin.
5. **Sin comprobante de pago**: No hay forma de descargar un recibo en PDF.

## Decisiones de Negocio

| Decisión | Elección |
|---|---|
| Días de facturación | Fecha Real con `fecha_corte` por cliente en `Suscripcion` |
| Asignación de `fecha_corte` | SuperAdmin lo asigna manualmente al crear la suscripción |
| `fecha_corte` editable | No, se fija al crear |
| Pago atrasado | Período nuevo cuenta desde `fecha_renovacion` original |
| Primer período prorrateado | Sí, sistema calcula automáticamente |
| Estructura primer pago | Solo prorrateo (no incluye mes completo adelantado) |
| Primer `fecha_renovacion` | Sistema calcula: próximo `fecha_corte` después de `fecha_inicio` |
| Anual + `fecha_corte` | Mes = `fecha_inicio.month`, día = `fecha_corte`, cada año |
| Ventas adicionales | `tipo_pago=ADICIONAL`, no toca Suscripcion |
| ADICIONAL genera automático | No, solo manual vía SuperAdmin |
| ADICIONAL expiración paquete | `fecha_vencimiento=None` |
| ADICIONAL historial | Sí, con `periodo_mes/ano = fecha actual` |
| `suscripcion.precio_pagado` | No se actualiza al confirmar |
| `fecha_pago` | `auto_now_add=True` (sin fecha histórica) |
| Numeración de recibos | UUID del Pago (`REC-{pago.id}`) |
| Formato PDF | Solo `reportlab` programático, sin HTML |
| Interfaz | Solo API endpoints, sin templates |

## Archivos a Modificar

### `apps/subscriptions/models.py`

Agregar campo `fecha_corte` a `Suscripcion`:

```python
from django.core.validators import MaxValueValidator

fecha_corte = models.PositiveSmallIntegerField(
    validators=[MaxValueValidator(28)],
    null=True,
    blank=True,
    help_text="Día fijo de facturación (1-28). Se asigna al crear y no cambia."
)
```

### `apps/pagos/serializers.py`

**`PagoSerializer`**: Eliminar `"fecha_corte"` de `fields` y `read_only_fields`.

**`PagoDetailSerializer`**: Eliminar `"fecha_corte"` de `fields` y `read_only_fields`.

**Nuevo `PagoCreateSerializer`**:

```python
class PagoCreateSerializer(CleanModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    plan_nombre = serializers.CharField(source="plan.nombre", read_only=True)

    class Meta:
        model = Pago
        fields = [
            "id", "empresa", "empresa_nombre", "suscripcion", "plan", "plan_nombre",
            "monto", "moneda", "tipo_pago", "metodo_pago", "referencia",
            "observaciones", "estado", "creado_at",
        ]
        read_only_fields = ["id", "estado", "creado_at"]
        extra_kwargs = {
            "monto": {"required": False},
            "empresa": {"required": True},
            "suscripcion": {"required": True},
            "plan": {"required": True},
        }
```

### `apps/pagos/views.py`

**`get_serializer_class()`**: Agregar:

```python
if self.action == 'create':
    return PagoCreateSerializer
```

**`create()`**: Reemplazar:

```python
def create(self, request, *args, **kwargs):
    return super().create(request, *args, **kwargs)
```

**`perform_create()`**: Agregar lógica de prorrateo:

```python
def perform_create(self, serializer):
    empresa = serializer.validated_data['empresa']
    suscripcion = serializer.validated_data['suscripcion']

    if not empresa.activa:
        raise ValidationError({"empresa": "La empresa no está activa."})
    if not suscripcion:
        raise ValidationError({"suscripcion": "La empresa debe tener una suscripción."})
    if suscripcion.estado not in [Suscripcion.ESTADO_ACTIVA, Suscripcion.ESTADO_VENCIDA, Suscripcion.ESTADO_SUSPENDIDA]:
        raise ValidationError({"suscripcion": "La suscripción no está en un estado válido."})

    monto = serializer.validated_data.get('monto')

    if monto is None:
        es_primer_pago = not Pago.objects.filter(
            suscripcion=suscripcion,
            estado=Pago.ESTADO_CONFIRMADO,
        ).exists()

        if es_primer_pago and suscripcion.fecha_corte:
            monto = self._calcular_monto_prorrateado(suscripcion)
            serializer.save(monto=monto)
            return

    serializer.save()


def _calcular_monto_prorrateado(self, suscripcion):
    from datetime import date
    from dateutil.relativedelta import relativedelta
    from decimal import Decimal
    from calendar import isleap

    fecha_inicio = suscripcion.fecha_inicio
    corte = suscripcion.fecha_corte
    plan = suscripcion.plan

    if fecha_inicio.day <= corte:
        primer_corte = date(fecha_inicio.year, fecha_inicio.month, corte)
    else:
        mes_sig = fecha_inicio + relativedelta(months=1)
        primer_corte = date(mes_sig.year, mes_sig.month, corte)

    if fecha_inicio.day >= corte:
        corte_anterior = date(fecha_inicio.year, fecha_inicio.month, corte)
    else:
        mes_ant = fecha_inicio - relativedelta(months=1)
        corte_anterior = date(mes_ant.year, mes_ant.month, corte)

    dias_periodo = (primer_corte - corte_anterior).days
    dias_usados = (primer_corte - fecha_inicio).days

    if suscripcion.ciclo == Suscripcion.CICLO_ANUAL:
        year = fecha_inicio.year
        dias_anio = 366 if isleap(year) else 365
        return (plan.precio_anual * Decimal(dias_usados) / Decimal(dias_anio)).quantize(Decimal('0.01'))

    return (plan.precio_mensual * Decimal(dias_usados) / Decimal(dias_periodo)).quantize(Decimal('0.01'))
```

**`_confirmar_pago_internamente()`**: Reescribir:

```python
def _confirmar_pago_internamente(self, pago, request):
    if pago.estado != Pago.ESTADO_PENDIENTE:
        return Response(
            {"error": "Solo se pueden confirmar pagos en estado PENDIENTE."},
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
        pago.estado = Pago.ESTADO_CONFIRMADO
        pago.confirmado_por = request.user
        pago.fecha_confirmacion = timezone.now()
        pago.save()

        suscripcion = pago.suscripcion

        if pago.tipo_pago == Pago.TIPO_RENOVACION:
            nueva_fecha_inicio = suscripcion.fecha_renovacion
            periodo_mes = nueva_fecha_inicio.month
            periodo_ano = nueva_fecha_inicio.year

            if suscripcion.ciclo == Suscripcion.CICLO_ANUAL:
                nueva_fecha_renovacion = nueva_fecha_inicio + relativedelta(years=1)
            else:
                nueva_fecha_renovacion = nueva_fecha_inicio + relativedelta(months=1)

            existe_historial = HistorialPago.objects.filter(
                empresa=pago.empresa,
                suscripcion=suscripcion,
                periodo_mes=periodo_mes,
                periodo_ano=periodo_ano,
                pago__tipo_pago=Pago.TIPO_RENOVACION,
            ).exists()

            if existe_historial:
                return Response(
                    {"error": f"Ya existe un pago confirmado para {periodo_mes}/{periodo_ano}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            actualizadas = Suscripcion.objects.filter(
                id=suscripcion.id,
                fecha_renovacion=suscripcion.fecha_renovacion,
            ).update(
                fecha_inicio=nueva_fecha_inicio,
                fecha_renovacion=nueva_fecha_renovacion,
                estado=Suscripcion.ESTADO_ACTIVA,
                plan=pago.plan,
            )

            if actualizadas == 0:
                return Response(
                    {"error": "La suscripción fue modificada por otro proceso."},
                    status=status.HTTP_409_CONFLICT
                )

            suscripcion.refresh_from_db()

            fecha_vencimiento = timezone.make_aware(
                datetime.combine(nueva_fecha_renovacion, datetime.min.time())
            )

            paquete = PaqueteComprobantes.objects.create(
                empresa=pago.empresa,
                suscripcion=suscripcion,
                plan=pago.plan,
                total_comprobantes=pago.plan.limite_comprobantes,
                comprobantes_usados=0,
                estado=PaqueteComprobantes.ESTADO_ACTIVO,
                origen=PaqueteComprobantes.ORIGEN_SUSCRIPCION,
                fecha_vencimiento=fecha_vencimiento,
            )

            historial = HistorialPago.objects.create(
                empresa=pago.empresa,
                suscripcion=suscripcion,
                plan=pago.plan,
                pago=pago,
                paquete=paquete,
                periodo_mes=periodo_mes,
                periodo_ano=periodo_ano,
                monto_pagado=pago.monto,
                comprobantes_asignados=pago.plan.limite_comprobantes,
            )

        else:  # ADICIONAL
            paquete = PaqueteComprobantes.objects.create(
                empresa=pago.empresa,
                suscripcion=suscripcion,
                plan=pago.plan,
                total_comprobantes=pago.plan.limite_comprobantes,
                comprobantes_usados=0,
                estado=PaqueteComprobantes.ESTADO_ACTIVO,
                origen=PaqueteComprobantes.ORIGEN_ADICIONAL,
                fecha_vencimiento=None,
            )

            ahora = timezone.now()
            historial = HistorialPago.objects.create(
                empresa=pago.empresa,
                suscripcion=suscripcion,
                plan=pago.plan,
                pago=pago,
                paquete=paquete,
                periodo_mes=ahora.month,
                periodo_ano=ahora.year,
                monto_pagado=pago.monto,
                comprobantes_asignados=pago.plan.limite_comprobantes,
            )

    serializer = PagoDetailSerializer(pago)
    return Response({
        "pago": serializer.data,
        "suscripcion": {
            "id": str(suscripcion.id),
            "estado": suscripcion.estado,
            "fecha_inicio": str(suscripcion.fecha_inicio),
            "fecha_renovacion": str(suscripcion.fecha_renovacion),
        },
        "paquete": {
            "id": str(paquete.id),
            "total_comprobantes": paquete.total_comprobantes,
            "estado": paquete.estado,
        },
        "historial": HistorialPagoSerializer(historial).data,
    })
```

**Eliminar endpoint `confirmar`** (deprecado).

**Agregar endpoints PDF**:

```python
from rest_framework.decorators import action
from django.http import FileResponse

@action(detail=True, methods=['get'], url_path='pdf/a4')
def pdf_a4(self, request, pk=None):
    pago = self.get_object()
    pdf_file = generar_pdf_a4(pago)
    return FileResponse(
        pdf_file, content_type='application/pdf',
        as_attachment=True,
        filename=f"comprobante-{pago.id}-a4.pdf"
    )

@action(detail=True, methods=['get'], url_path='pdf/80mm')
def pdf_80mm(self, request, pk=None):
    pago = self.get_object()
    pdf_file = generar_pdf_80mm(pago)
    return FileResponse(
        pdf_file, content_type='application/pdf',
        as_attachment=True,
        filename=f"comprobante-{pago.id}-80mm.pdf"
    )
```

### `apps/pagos/pdf.py` (NUEVO)

```python
from io import BytesIO
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ANCHO_80MM = 80 * mm
MARGEN_80MM = 4 * mm
ALTO_PAGINA_80MM = 150 * mm


def generar_pdf_a4(pago):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    # Encabezado
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2*cm, y, "COMPROBANTE DE PAGO")
    y -= 30

    c.setFont("Helvetica", 10)
    c.drawString(2*cm, y, f"Recibo No. REC-{pago.id}")
    y -= 20

    c.line(2*cm, y, width - 2*cm, y)
    y -= 25

    # Empresa
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y, "Empresa")
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(2*cm, y, pago.empresa.nombre)
    y -= 14
    c.drawString(2*cm, y, f"RNC: {pago.empresa.rnc}")
    y -= 25

    c.line(2*cm, y, width - 2*cm, y)
    y -= 25

    # Detalle
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y, "Detalle del Pago")
    y -= 20

    datos = [
        ("Plan", pago.plan.nombre),
        ("Ciclo", pago.suscripcion.ciclo),
        ("Tipo", dict(Pago.TIPOS_PAGO).get(pago.tipo_pago, pago.tipo_pago)),
        ("Monto", f"{pago.monto} {pago.moneda}"),
        ("Método de pago", dict(Pago.METODOS_PAGO).get(pago.metodo_pago, pago.metodo_pago)),
        ("Referencia", pago.referencia or "\u2014"),
        ("Estado", "CONFIRMADO"),
        ("Confirmado por", pago.confirmado_por.username if pago.confirmado_por else "\u2014"),
        ("Fecha de pago", pago.fecha_pago.strftime("%d/%m/%Y %H:%M") if pago.fecha_pago else "\u2014"),
        ("Fecha de confirmación", pago.fecha_confirmacion.strftime("%d/%m/%Y %H:%M") if pago.fecha_confirmacion else "\u2014"),
    ]

    c.setFont("Helvetica", 10)
    for label, value in datos:
        c.drawString(2*cm, y, label)
        c.drawRightString(width - 2*cm, y, str(value))
        y -= 16

    y -= 10
    c.line(2*cm, y, width - 2*cm, y)
    y -= 20

    # Pie
    c.setFont("Helvetica", 7)
    c.setFillGray(0.5, 0.5, 0.5)
    c.drawString(2*cm, y, f"ID interno: {pago.id}")
    y -= 12
    c.drawString(2*cm, y, "Este documento es un comprobante de pago interno.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def generar_pdf_80mm(pago):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(ANCHO_80MM, ALTO_PAGINA_80MM))
    x = MARGEN_80MM
    y = ALTO_PAGINA_80MM - MARGEN_80MM
    ancho_texto = ANCHO_80MM - 2 * MARGEN_80MM

    c.setFont("Courier-Bold", 10)
    c.drawCentredString(ANCHO_80MM / 2, y, "COMPROBANTE DE PAGO")
    y -= 16

    c.setFont("Courier", 8)
    c.drawCentredString(ANCHO_80MM / 2, y, f"REC-{pago.id}")
    y -= 20

    c.line(x, y, x + ancho_texto, y)
    y -= 14

    c.drawString(x, y, f"Empresa: {pago.empresa.nombre}")
    y -= 12
    c.drawString(x, y, f"RNC: {pago.empresa.rnc}")
    y -= 16

    c.line(x, y, x + ancho_texto, y)
    y -= 14

    lineas = [
        f"Plan:      {pago.plan.nombre}",
        f"Ciclo:     {pago.suscripcion.ciclo}",
        f"Tipo:      {dict(Pago.TIPOS_PAGO).get(pago.tipo_pago, pago.tipo_pago)}",
        f"Metodo:    {dict(Pago.METODOS_PAGO).get(pago.metodo_pago, pago.metodo_pago)}",
        f"Refer.:    {pago.referencia or '-'}",
        f"Monto:     {pago.monto} {pago.moneda}",
        f"Estado:    CONFIRMADO",
    ]

    for linea in lineas:
        c.drawString(x, y, linea)
        y -= 12

    if pago.fecha_confirmacion:
        y -= 4
        c.line(x, y, x + ancho_texto, y)
        y -= 14
        c.drawString(x, y, f"Confirmado: {pago.confirmado_por.username if pago.confirmado_por else '--'}")
        y -= 12
        c.drawString(x, y, f"Fecha: {pago.fecha_confirmacion.strftime('%d/%m/%Y %H:%M')}")

    y -= 16
    c.line(x, y, x + ancho_texto, y)
    y -= 14

    c.setFont("Courier", 6)
    c.drawString(x, y, f"ID: {pago.id}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
```

### `apps/pagos/tasks.py`

```python
@shared_task(name='pagos.generar_pagos_automaticos')
def generar_pagos_automaticos():
    ahora = timezone.now()
    fecha_limite = ahora + timedelta(days=15)

    logger.info(f"[PAGOS] Iniciando generación automática. Rango: {ahora.date()} \u2013 {fecha_limite.date()}")

    suscripciones = Suscripcion.objects.filter(
        estado__in=[
            Suscripcion.ESTADO_ACTIVA,
            Suscripcion.ESTADO_VENCIDA,
            Suscripcion.ESTADO_SUSPENDIDA,
        ],
        fecha_renovacion__lte=fecha_limite,
        fecha_renovacion__gt=ahora,
    ).select_related('empresa', 'plan')

    total = suscripciones.count()
    pagos_creados = 0
    saltados = 0
    errores = 0

    for suscripcion in suscripciones:
        empresa = suscripcion.empresa
        rnc = getattr(empresa, 'rnc', str(empresa.id))

        try:
            # Guardia 1: ya existe una renovación PENDIENTE
            if Pago.objects.filter(
                empresa_id=empresa.id,
                estado=Pago.ESTADO_PENDIENTE,
                tipo_pago=Pago.TIPO_RENOVACION,
            ).exists():
                saltados += 1
                continue

            # Guardia 2: debe tener al menos un pago confirmado previo
            if not Pago.objects.filter(
                suscripcion=suscripcion,
                estado=Pago.ESTADO_CONFIRMADO,
            ).exists():
                saltados += 1
                continue

            monto = _seleccionar_monto(suscripcion)
            if monto is None:
                errores += 1
                logger.error(f"[PAGOS] No se pudo determinar el monto. empresa_id={empresa.id} rnc={rnc}")
                continue

            with transaction.atomic():
                Pago.objects.create(
                    empresa=empresa,
                    suscripcion=suscripcion,
                    plan=suscripcion.plan,
                    monto=monto,
                    moneda=Pago.MONEDA_DOP,
                    metodo_pago='',
                    referencia='',
                    estado=Pago.ESTADO_PENDIENTE,
                )

            pagos_creados += 1

        except Exception as exc:
            errores += 1
            logger.error(f"[PAGOS] Error inesperado para rnc={rnc}: {exc}", exc_info=True)

    # Status final
    if errores == 0 and pagos_creados > 0:
        status = 'success'
    elif errores == 0 and pagos_creados == 0:
        status = 'no_action_needed'
    elif pagos_creados > 0:
        status = 'partial_success'
    else:
        status = 'failed'

    resultado = {
        'status': status,
        'pagos_creados': pagos_creados,
        'saltados': saltados,
        'errores': errores,
        'total_procesadas': total,
    }

    logger.info(f"[PAGOS] Generación completada: {resultado}")
    return resultado
```

### `requirements.txt`

Agregar:
```
reportlab==4.2
```

## Migraciones

Un solo archivo con 3 operaciones:

```python
operations = [
    migrations.AddField(
        model_name='suscripcion',
        name='fecha_corte',
        field=models.PositiveSmallIntegerField(
            null=True, blank=True,
            validators=[django.core.validators.MaxValueValidator(28)]
        ),
    ),
    migrations.AlterUniqueTogether(
        name='historialpago',
        unique_together=set(),
    ),
    migrations.SeparateDatabaseAndState(
        state_operations=[
            migrations.RemoveField(
                model_name='pago',
                name='fecha_corte',
            ),
        ],
        database_operations=[],
    ),
]
```

## Tests a Actualizar

**`apps/pagos/tests/test_tasks.py`**:
- `_make_plan()`: eliminar `fecha_corte` y `plan.fecha_corte` (mantener `del plan.precio`)
- Eliminar clase `TestCalcularPeriodo` (4 tests)
- `TestGenerarPagosAutomaticos`: agregar `MockPago.TIPO_RENOVACION = 'RENOVACION'`
- Actualizar mock de `Pago.objects.filter` para incluir `tipo_pago=RENOVACION` en Guardia 1
- Agregar mock para Guardia 2: `Pago.objects.filter(suscripcion=..., estado=CONFIRMADO).exists()`

## Orden de Implementación

1. `requirements.txt` + `reportlab`
2. Modelo `Suscripcion.fecha_corte`
3. `serializers.py` (limpiar `fecha_corte`, + `PagoCreateSerializer`)
4. `views.py` (create, prorrateo, `_confirmar_pago_internamente`, PDF endpoints)
5. `tasks.py` (limpiar `fecha_corte`, guardias)
6. `pdf.py` (generación PDF)
7. Tests
8. Migración
9. `python manage.py migrate && python manage.py test pagos.tests`
