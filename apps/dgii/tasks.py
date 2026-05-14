from celery import shared_task

from dgii.services import emitir_ecf


@shared_task(bind=True, max_retries=5)
def reintentar_envio_ecf(self, comprobante_id):
    """
    Reintenta envio de e-CF en contingencia con backoff.
    """
    try:
        emitir_ecf(comprobante_id, forzar_reintento=True)
    except Exception as exc:
        countdowns = [30, 120, 600, 3600, 14400]
        intento = min(self.request.retries, len(countdowns) - 1)
        raise self.retry(exc=exc, countdown=countdowns[intento])
