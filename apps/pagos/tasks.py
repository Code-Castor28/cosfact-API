"""
Tasks de Celery para la app de pagos.

Incluye:
- Generación automática de pagos pendientes
- Notificaciones de pagos próximos a vencer
"""
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
import logging

from .models import Pago, HistorialPago
from subscriptions.models import Suscripcion
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


def _seleccionar_monto(suscripcion) -> Decimal | None:
    """
    Devuelve el monto a cobrar para una suscripción, o None si no se puede determinar.

    Orden de prioridad:
      1. precio_mensual / precio_anual del plan según el ciclo de la suscripción.
      2. suscripcion.precio_pagado como fallback (precio histórico confirmado).

    Retorna None si ninguna fuente produce un Decimal > 0.
    """
    ciclo = (suscripcion.ciclo or '').strip().upper()

    candidatos = []

    if ciclo in (Suscripcion.CICLO_MENSUAL, 'MONTHLY'):
        candidatos.append(('plan.precio_mensual', getattr(
            suscripcion.plan, 'precio_mensual', None)))
    elif ciclo in (Suscripcion.CICLO_ANUAL, 'ANNUAL'):
        candidatos.append(('plan.precio_anual', getattr(
            suscripcion.plan, 'precio_anual', None)))
    else:
        # Ciclo desconocido: intentar ambos precios del plan antes del fallback
        candidatos.append(('plan.precio_mensual', getattr(
            suscripcion.plan, 'precio_mensual', None)))
        candidatos.append(('plan.precio_anual',   getattr(
            suscripcion.plan, 'precio_anual',   None)))

    # Fallback: precio que la empresa pagó en su última renovación
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


def _calcular_periodo(ahora, fecha_corte: int) -> tuple[int, int]:
    """
    Devuelve (periodo_mes, periodo_ano) para la fecha dada y el día de corte del plan.

    Si today <= fecha_corte  → el período corriente es el mes actual.
    Si today >  fecha_corte  → el período corriente es el mes siguiente.
    """
    if ahora.day <= fecha_corte:
        return ahora.month, ahora.year
    siguiente = ahora + timedelta(days=30)
    return siguiente.month, siguiente.year


@shared_task(name='pagos.generar_pagos_automaticos')
def generar_pagos_automaticos():
    """
    Crea Pago PENDIENTE para suscripciones que vencen en ~15 días.

    Lógica:
    - Busca: Suscripciones con estado ACTIVA | VENCIDA | SUSPENDIDA
    - Filtra: fecha_renovacion en rango (HOY, HOY + 15 días]
    - Valida:
        * No exista otro Pago PENDIENTE del cliente
        * No exista HistorialPago confirmado para ese período
    - Crea: Pago(estado=PENDIENTE, monto=<precio según ciclo>, metodo_pago='')

    Se ejecuta: Diariamente a las 00:00 (vía celery beat)

    Retorna:
        dict con claves: status, pagos_creados, errores, saltados, total_procesadas
    """
    ahora = timezone.now()
    fecha_limite = ahora + timedelta(days=15)

    logger.info(
        f"[PAGOS] Iniciando generación automática de pagos. "
        f"Rango: {ahora.date()} – {fecha_limite.date()}"
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
            # ── Guardia 1: no duplicar pago PENDIENTE ──────────────────────────
            if Pago.objects.filter(
                empresa_id=empresa.id,
                estado=Pago.ESTADO_PENDIENTE,
            ).exists():
                logger.debug(
                    f"[PAGOS] Saltando {rnc}: ya existe Pago PENDIENTE")
                saltados += 1
                continue

            # ── Período de facturación ─────────────────────────────────────────
            fecha_corte = int(getattr(suscripcion.plan, 'fecha_corte', 1) or 1)
            periodo_mes, periodo_ano = _calcular_periodo(ahora, fecha_corte)

            # ── Guardia 2: no duplicar historial ──────────────────────────────
            if HistorialPago.objects.filter(
                empresa_id=empresa.id,
                periodo_mes=periodo_mes,
                periodo_ano=periodo_ano,
            ).exists():
                logger.debug(
                    f"[PAGOS] Saltando {rnc}: "
                    f"ya existe HistorialPago para {periodo_mes}/{periodo_ano}"
                )
                saltados += 1
                continue

            # ── Monto ─────────────────────────────────────────────────────────
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

            # ── Crear pago ────────────────────────────────────────────────────
            with transaction.atomic():
                pago = Pago.objects.create(
                    empresa=suscripcion.empresa,
                    suscripcion=suscripcion,
                    plan=suscripcion.plan,
                    monto=monto,
                    moneda=Pago.MONEDA_DOP,
                    metodo_pago='',   # se rellena al confirmar
                    referencia='',
                    fecha_pago=ahora,
                    fecha_corte=fecha_corte,
                    estado=Pago.ESTADO_PENDIENTE,
                )

            logger.info(
                f"[PAGOS] Pago creado: id={pago.id} rnc={rnc} "
                f"monto={pago.monto} {pago.moneda} "
                f"ciclo={suscripcion.ciclo} periodo={periodo_mes}/{periodo_ano}"
            )
            pagos_creados += 1

        except Exception as exc:
            errores += 1
            logger.error(
                f"[PAGOS] Error inesperado para rnc={rnc}: {exc}",
                exc_info=True,
            )

    # ── Status final ──────────────────────────────────────────────────────────
    if errores == 0 and pagos_creados > 0:
        status = 'success'
    elif errores == 0 and pagos_creados == 0:
        # Puede ser correcto (todos ya tenían PENDIENTE / historial)
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


@shared_task(name='pagos.notificar_pagos_proximos')
def notificar_pagos_proximos():
    """
    Notifica a empresas sobre pagos próximos a vencer (7 días antes).

    [IMPLEMENTAR] En futuro:
    - Enviar email a admin empresa
    - Enviar SMS si configurado
    - Crear notificación en dashboard
    """
    logger.info("[PAGOS] Iniciando notificación de pagos próximos")
    # TODO: Implementar notificaciones
    pass
