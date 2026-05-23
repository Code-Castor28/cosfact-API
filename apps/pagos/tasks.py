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
from decimal import Decimal

logger = logging.getLogger(__name__)


@shared_task(name='pagos.generar_pagos_automaticos')
def generar_pagos_automaticos():
    """
    Crea Pago PENDIENTE para suscripciones que vencen en ~15 días.

    Lógica:
    - Busca: Suscripciones con estado != CANCELADA
    - Filtra: fecha_renovacion en rango (HOY, HOY + 15 días]
    - Valida: 
        * No exista otro Pago PENDIENTE del cliente
        * No exista HistorialPago confirmado para ese período
    - Crea: Pago(estado=PENDIENTE, monto=plan.precio, metodo_pago='')

    Se ejecuta: Diariamente a las 00:00 (vía celery beat)

    Retorna:
        dict: { "status": "success", "pagos_creados": int, "errores": int }
    """
    ahora = timezone.now()
    fecha_limite = ahora + timedelta(days=15)

    logger.info(
        f"[PAGOS] Iniciando generación automática de pagos. "
        f"Rango: {ahora.date()} a {fecha_limite.date()}"
    )

    # Buscar suscripciones que vencen en 15 días
    suscripciones = Suscripcion.objects.filter(
        estado__in=[
            Suscripcion.ESTADO_ACTIVA,
            Suscripcion.ESTADO_VENCIDA,
            Suscripcion.ESTADO_SUSPENDIDA,
        ],
        fecha_renovacion__lte=fecha_limite,
        fecha_renovacion__gt=ahora,
    ).select_related('empresa', 'plan')

    pagos_creados = 0
    errores = 0

    for suscripcion in suscripciones:
        try:
            # Validar: no existe pago PENDIENTE ya
            existe_pendiente = Pago.objects.filter(
                empresa=suscripcion.empresa,
                estado=Pago.ESTADO_PENDIENTE,
            ).exists()

            if existe_pendiente:
                logger.debug(
                    f"[PAGOS] Saltando {suscripcion.empresa.rnc}: "
                    f"ya existe Pago PENDIENTE"
                )
                continue

            # Calcular período
            fecha_pago = ahora
            fecha_corte = suscripcion.plan.fecha_corte if hasattr(
                suscripcion.plan, 'fecha_corte'
            ) else 1

            if fecha_pago.day <= fecha_corte:
                periodo_mes = fecha_pago.month
                periodo_ano = fecha_pago.year
            else:
                siguiente = fecha_pago + timedelta(days=30)
                periodo_mes = siguiente.month
                periodo_ano = siguiente.year

            # Validar: no existe HistorialPago para ese período
            existe_historial = HistorialPago.objects.filter(
                empresa=suscripcion.empresa,
                periodo_mes=periodo_mes,
                periodo_ano=periodo_ano,
            ).exists()

            if existe_historial:
                logger.debug(
                    f"[PAGOS] Saltando {suscripcion.empresa.rnc}: "
                    f"ya existe HistorialPago para {periodo_mes}/{periodo_ano}"
                )
                continue

            # Crear Pago
            with transaction.atomic():
                # Obtener monto del plan según el ciclo de la suscripción
                monto = None
                ciclo_suscripcion = (suscripcion.ciclo or '').strip().upper()
                if ciclo_suscripcion in (Suscripcion.CICLO_MENSUAL, 'MONTHLY'):
                    monto = getattr(suscripcion.plan, 'precio_mensual', None)
                elif ciclo_suscripcion in (Suscripcion.CICLO_ANUAL, 'ANNUAL'):
                    monto = getattr(suscripcion.plan, 'precio_anual', None)

                # Si el plan no tiene precio para el ciclo, intentar usar el precio pagado (histórico)
                if monto is None or (isinstance(monto, Decimal) and monto <= Decimal('0')):
                    precio_pagado = getattr(suscripcion, 'precio_pagado', None)
                    if precio_pagado and precio_pagado > Decimal('0'):
                        monto = precio_pagado

                # Log de diagnóstico: mostrar plan, ciclo y precios antes de validar
                try:
                    logger.info(
                        f"[PAGOS] Plan={suscripcion.plan.nombre} "
                        f"plan_id={suscripcion.plan.id} "
                        f"ciclo_suscripcion={suscripcion.ciclo} "
                        f"ciclo_suscripcion_normalizado={ciclo_suscripcion} "
                        f"ciclo_plan={getattr(suscripcion.plan, 'ciclo_disponible', None)} "
                        f"precio_mensual={getattr(suscripcion.plan, 'precio_mensual', None)} "
                        f"precio_anual={getattr(suscripcion.plan, 'precio_anual', None)} "
                        f"precio_pagado_suscripcion={getattr(suscripcion, 'precio_pagado', None)} "
                        f"monto_seleccionado={monto} "
                        f"tipo_monto={type(monto)}"
                    )
                except Exception:
                    logger.debug(
                        f"[PAGOS] Error al loggear precios para Plan {getattr(suscripcion.plan, 'id', 'unknown')}")

                # Validar monto final
                try:
                    if monto is None or Decimal(monto) <= Decimal('0'):
                        logger.warning(
                            f"[PAGOS] Plan {suscripcion.plan.id} no tiene precio. "
                            f"Saltando {suscripcion.empresa.rnc}"
                        )
                        continue
                except Exception:
                    logger.warning(
                        f"[PAGOS] Precio inválido para Plan {suscripcion.plan.id}: {monto}. "
                        f"Saltando {suscripcion.empresa.rnc}"
                    )
                    continue

                pago = Pago.objects.create(
                    empresa=suscripcion.empresa,
                    suscripcion=suscripcion,
                    plan=suscripcion.plan,
                    monto=monto,
                    moneda=Pago.MONEDA_DOP,  # Default DOP
                    metodo_pago='',  # Vacío, se rellenará al confirmar
                    referencia='',
                    fecha_pago=ahora,
                    fecha_corte=fecha_corte,
                    estado=Pago.ESTADO_PENDIENTE,
                )

                logger.info(
                    f"[PAGOS] Pago creado para {suscripcion.empresa.rnc} "
                    f"({pago.id}): ${pago.monto} {pago.moneda}"
                )
                pagos_creados += 1

        except Exception as e:
            errores += 1
            logger.error(
                f"[PAGOS] Error creando pago para "
                f"{suscripcion.empresa.rnc}: {str(e)}",
                exc_info=True
            )
            continue

    resultado = {
        "status": "success",
        "pagos_creados": pagos_creados,
        "errores": errores,
        "total_procesadas": suscripciones.count(),
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
