"""
Tasks de Celery para la app de pagos.
"""
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
import logging

from .models import Pago
from subscriptions.models import Suscripcion
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


def _seleccionar_monto(suscripcion) -> Decimal | None:
    ciclo = (suscripcion.ciclo or '').strip().upper()

    candidatos = []

    if ciclo in (Suscripcion.CICLO_MENSUAL, 'MONTHLY'):
        candidatos.append(('plan.precio_mensual', getattr(
            suscripcion.plan, 'precio_mensual', None)))
    elif ciclo in (Suscripcion.CICLO_ANUAL, 'ANNUAL'):
        candidatos.append(('plan.precio_anual', getattr(
            suscripcion.plan, 'precio_anual', None)))
    else:
        candidatos.append(('plan.precio_mensual', getattr(
            suscripcion.plan, 'precio_mensual', None)))
        candidatos.append(('plan.precio_anual', getattr(
            suscripcion.plan, 'precio_anual', None)))

    candidatos.append(('suscripcion.precio_pagado', getattr(
        suscripcion, 'precio_pagado', None)))

    for fuente, valor in candidatos:
        if valor is None:
            continue
        try:
            d = Decimal(str(valor))
        except (InvalidOperation, ValueError, TypeError):
            logger.debug(
                f"[PAGOS] _seleccionar_monto: valor no convertible a Decimal "
                f"fuente={fuente} valor={valor!r} "
                f"empresa_id={suscripcion.empresa_id}"
            )
            continue
        if d > Decimal('0'):
            logger.debug(
                f"[PAGOS] _seleccionar_monto: usando {fuente}={d} "
                f"ciclo={ciclo} empresa_id={suscripcion.empresa_id}"
            )
            return d

    return None


@shared_task(name='pagos.generar_pagos_automaticos')
def generar_pagos_automaticos():
    ahora = timezone.now()
    fecha_limite = ahora + timedelta(days=15)

    logger.info(
        f"[PAGOS] Iniciando generacion automatica de pagos. "
        f"Rango: {ahora.date()} \u2013 {fecha_limite.date()}"
    )

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
        rnc = getattr(suscripcion.empresa, 'rnc', str(empresa.id))

        try:
            if Pago.objects.filter(
                empresa_id=empresa.id,
                estado=Pago.ESTADO_PENDIENTE,
                tipo_pago=Pago.TIPO_RENOVACION,
            ).exists():
                logger.debug(
                    f"[PAGOS] Saltando {rnc}: ya existe Pago PENDIENTE")
                saltados += 1
                continue

            if not Pago.objects.filter(
                suscripcion=suscripcion,
                estado=Pago.ESTADO_CONFIRMADO,
            ).exists():
                logger.debug(
                    f"[PAGOS] Saltando {rnc}: no tiene pagos confirmados previos")
                saltados += 1
                continue

            monto = _seleccionar_monto(suscripcion)

            if monto is None:
                errores += 1
                logger.error(
                    f"[PAGOS] No se pudo determinar el monto. "
                    f"empresa_id={empresa.id} rnc={rnc} "
                    f"plan={suscripcion.plan} ciclo={suscripcion.ciclo!r} "
                    f"precio_mensual={getattr(suscripcion.plan, 'precio_mensual', None)!r} "
                    f"precio_anual={getattr(suscripcion.plan, 'precio_anual', None)!r} "
                    f"precio_pagado={getattr(suscripcion, 'precio_pagado', None)!r}"
                )
                continue

            with transaction.atomic():
                Pago.objects.create(
                    empresa=suscripcion.empresa,
                    suscripcion=suscripcion,
                    plan=suscripcion.plan,
                    monto=monto,
                    moneda=Pago.MONEDA_DOP,
                    metodo_pago='',
                    referencia='',
                    estado=Pago.ESTADO_PENDIENTE,
                    fecha_corte=suscripcion.fecha_corte,
                )

            logger.info(
                f"[PAGOS] Pago creado: rnc={rnc} "
                f"monto={monto} {Pago.MONEDA_DOP} "
                f"ciclo={suscripcion.ciclo}"
            )
            pagos_creados += 1

        except Exception as exc:
            errores += 1
            logger.error(
                f"[PAGOS] Error inesperado para rnc={rnc}: {exc}",
                exc_info=True,
            )

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

    logger.info(f"[PAGOS] Generacion completada: {resultado}")
    return resultado


@shared_task(name='pagos.notificar_pagos_proximos')
def notificar_pagos_proximos():
    logger.info("[PAGOS] Iniciando notificacion de pagos proximos")
    from notificaciones.tasks import alertar_suscripcion_vencimiento
    alertar_suscripcion_vencimiento.delay()
