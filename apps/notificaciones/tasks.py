import logging
from datetime import timedelta

from celery import shared_task
from django.template.loader import render_to_string
from django.utils import timezone

from .services import enviar_correo
from .models import LogNotificacion

logger = logging.getLogger(__name__)


@shared_task(name="notificaciones.enviar_recibo_pago")
def enviar_recibo_pago(pago_id):
    from pagos.models import Pago

    try:
        pago = Pago.objects.select_related("empresa", "suscripcion__plan").get(
            pk=pago_id
        )
    except Pago.DoesNotExist:
        logger.warning(f"[NOTIFICACIONES] Pago {pago_id} no encontrado")
        return

    empresa = pago.empresa
    destinatario = empresa.email

    if not destinatario:
        logger.warning(
            f"[NOTIFICACIONES] Empresa {empresa.id} sin email para recibo de pago"
        )
        return

    contexto = {
        "empresa_nombre": empresa.nombre or empresa.rnc,
        "monto": str(pago.monto),
        "moneda": pago.moneda,
        "fecha": pago.creado_at.strftime("%d/%m/%Y"),
        "referencia": pago.referencia or "N/A",
        "plan": pago.suscripcion.plan.nombre if pago.suscripcion else "N/A",
    }

    asunto = f"Recibo de pago {pago.referencia or ''}"
    cuerpo_html = render_to_string(
        "notificaciones/pago_confirmado.html", contexto
    )

    enviar_correo(
        destinatario=destinatario,
        asunto=asunto,
        cuerpo_html=cuerpo_html,
        empresa=empresa,
        tipo=LogNotificacion.TIPO_RECIBO_PAGO,
    )


@shared_task(name="notificaciones.alertar_balance_bajo")
def alertar_balance_bajo():
    from subscriptions.models import PaqueteComprobantes
    from empresas.models import Empresa

    umbral_alerta = 20
    fecha_limite = timezone.now() - timedelta(hours=24)

    paquetes = PaqueteComprobantes.objects.filter(
        estado="ACTIVO",
        creado_at__lte=fecha_limite,
    ).select_related("empresa")

    for paquete in paquetes:
        total = paquete.cantidad_inicial
        usado = paquete.cantidad_consumida
        if total <= 0:
            continue
        porcentaje = ((total - usado) / total) * 100
        if porcentaje > umbral_alerta:
            continue

        empresa = paquete.empresa
        destinatario = empresa.email
        if not destinatario:
            continue

        contexto = {
            "empresa_nombre": empresa.nombre or empresa.rnc,
            "restantes": total - usado,
            "total": total,
            "porcentaje": f"{porcentaje:.0f}",
        }

        asunto = "Balance de comprobantes bajo"
        cuerpo_html = render_to_string(
            "notificaciones/balance_bajo.html", contexto
        )

        enviar_correo(
            destinatario=destinatario,
            asunto=asunto,
            cuerpo_html=cuerpo_html,
            empresa=empresa,
            tipo=LogNotificacion.TIPO_BALANCE_BAJO,
        )


@shared_task(name="notificaciones.alertar_certificado_vencimiento")
def alertar_certificado_vencimiento():
    from empresas.models import CertificadoDigital

    dias_alerta = 30
    hoy = timezone.now().date()
    fecha_limite = hoy + timedelta(days=dias_alerta)

    certificados = CertificadoDigital.objects.filter(
        activo=True,
        fecha_vencimiento__lte=fecha_limite,
        fecha_vencimiento__gte=hoy,
    ).select_related("empresa")

    for cert in certificados:
        empresa = cert.empresa
        destinatario = empresa.email
        if not destinatario:
            continue

        dias_restantes = (cert.fecha_vencimiento - hoy).days

        contexto = {
            "empresa_nombre": empresa.nombre or empresa.rnc,
            "dias_restantes": dias_restantes,
            "fecha_vencimiento": cert.fecha_vencimiento.strftime("%d/%m/%Y"),
        }

        asunto = f"Certificado digital por vencer ({dias_restantes} días)"
        cuerpo_html = render_to_string(
            "notificaciones/certificado_por_vencer.html", contexto
        )

        enviar_correo(
            destinatario=destinatario,
            asunto=asunto,
            cuerpo_html=cuerpo_html,
            empresa=empresa,
            tipo=LogNotificacion.TIPO_CERTIFICADO_VENCER,
        )


@shared_task(name="notificaciones.alertar_suscripcion_vencimiento")
def alertar_suscripcion_vencimiento():
    from subscriptions.models import Suscripcion

    dias_alerta = 7
    hoy = timezone.now().date()
    fecha_limite = hoy + timedelta(days=dias_alerta)

    suscripciones = Suscripcion.objects.filter(
        estado=Suscripcion.ESTADO_ACTIVA,
        fecha_renovacion__lte=fecha_limite,
        fecha_renovacion__gte=hoy,
    ).select_related("empresa", "plan")

    for suscripcion in suscripciones:
        empresa = suscripcion.empresa
        destinatario = empresa.email
        if not destinatario:
            continue

        dias_restantes = (suscripcion.fecha_renovacion - hoy).days

        contexto = {
            "empresa_nombre": empresa.nombre or empresa.rnc,
            "dias_restantes": dias_restantes,
            "fecha_renovacion": suscripcion.fecha_renovacion.strftime("%d/%m/%Y"),
            "plan": suscripcion.plan.nombre if suscripcion.plan else "N/A",
        }

        asunto = f"Suscripción por vencer ({dias_restantes} días)"
        cuerpo_html = render_to_string(
            "notificaciones/suscripcion_por_vencer.html", contexto
        )

        enviar_correo(
            destinatario=destinatario,
            asunto=asunto,
            cuerpo_html=cuerpo_html,
            empresa=empresa,
            tipo=LogNotificacion.TIPO_SUSCRIPCION_VENCER,
        )
