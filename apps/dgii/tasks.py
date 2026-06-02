from celery import shared_task
from django.utils import timezone

from dgii.services import emitir_ecf
from webhooks.services import backoff_con_jitter


@shared_task(bind=True, max_retries=5)
def reintentar_envio_ecf(self, comprobante_id):
    try:
        emitir_ecf(comprobante_id, forzar_reintento=True)
    except Exception as exc:
        intento = min(self.request.retries, 4)
        countdown = backoff_con_jitter(intento)
        raise self.retry(exc=exc, countdown=countdown)


@shared_task(name="dgii.reintentar_contingencia")
def reintentar_contingencia():
    from comprobantes.models import Comprobante

    comprobantes = Comprobante.objects.filter(estado="CONTINGENCIA")
    for c in comprobantes:
        reintentar_envio_ecf.delay(c.id)
