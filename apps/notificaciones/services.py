import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import LogNotificacion

logger = logging.getLogger(__name__)


def enviar_correo(destinatario, asunto, cuerpo_html, cuerpo_texto="", empresa=None, tipo=None):
    try:
        msg = EmailMultiAlternatives(
            subject=asunto,
            body=cuerpo_texto or "",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destinatario],
        )
        msg.attach_alternative(cuerpo_html, "text/html")
        msg.send()

        if tipo and empresa:
            LogNotificacion.objects.create(
                empresa=empresa,
                destinatario=destinatario,
                tipo=tipo,
                asunto=asunto,
                estado=LogNotificacion.ESTADO_ENVIADO,
            )

        logger.info(f"[NOTIFICACIONES] Correo enviado a {destinatario}: {asunto}")
        return True

    except Exception as exc:
        logger.error(
            f"[NOTIFICACIONES] Error enviando correo a {destinatario}: {exc}",
            exc_info=True,
        )
        if tipo and empresa:
            LogNotificacion.objects.create(
                empresa=empresa,
                destinatario=destinatario,
                tipo=tipo,
                asunto=asunto,
                estado=LogNotificacion.ESTADO_FALLIDO,
                error_mensaje=str(exc)[:2000],
            )
        return False
