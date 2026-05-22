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
                # Obtener monto del plan
                monto = getattr(suscripcion.plan, 'precio', 0)
                if not monto:
                    logger.warning(
                        f"[PAGOS] Plan {suscripcion.plan.id} no tiene precio. "
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
