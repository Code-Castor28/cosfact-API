import hashlib
import hmac
import json
import logging
import random
import requests
from celery import shared_task
from django.utils import timezone

from .models import Webhook, WebhookEntrega

logger = logging.getLogger(__name__)

BACKOFF_BASE = [60, 300, 900, 3600, 14400]


def backoff_con_jitter(intento):
    base = BACKOFF_BASE[intento]
    jitter = random.uniform(0, base * 0.1)
    return int(base + jitter)


def disparar_webhook(empresa, evento, payload):
    webhooks = Webhook.objects.filter(
        empresa=empresa, activo=True, eventos__contains=evento
    )
    for wh in webhooks:
        entregar_webhook.delay(wh.id, evento, payload)


@shared_task(bind=True, max_retries=5)
def entregar_webhook(self, webhook_id, evento, payload):
    try:
        wh = Webhook.objects.get(id=webhook_id)
    except Webhook.DoesNotExist:
        logger.warning(f"[WEBHOOK] Webhook {webhook_id} no encontrado")
        return

    payload_str = json.dumps(payload, separators=(",", ":"), default=str)
    payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

    entrega = WebhookEntrega.objects.create(
        webhook=wh,
        evento=evento,
        payload_hash=payload_hash,
    )

    signature = hmac.new(
        wh.secret_hash.encode(), payload_str.encode(), hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-DerejSoft-Signature": f"sha256={signature}",
        "X-DerejSoft-Event": evento,
    }

    try:
        resp = requests.post(
            wh.url,
            data=payload_str,
            headers=headers,
            timeout=30,
        )
        entrega.ultimo_http_status = resp.status_code
        wh.ultimo_http_status = resp.status_code

        if 200 <= resp.status_code < 300:
            entrega.estado = WebhookEntrega.ESTADO_ENTREGADO
            entrega.entregado_at = timezone.now()
            wh.estado = Webhook.ESTADO_ACTIVO
        else:
            entrega.estado = WebhookEntrega.ESTADO_FALLIDO
            entrega.error_mensaje = f"HTTP {resp.status_code}: {resp.text[:500]}"
            wh.estado = Webhook.ESTADO_FALLANDO

    except requests.RequestException as exc:
        entrega.estado = WebhookEntrega.ESTADO_FALLIDO
        entrega.error_mensaje = str(exc)[:2000]
        wh.estado = Webhook.ESTADO_FALLANDO
        entrega.ultimo_http_status = 0

    entrega.intentos += 1
    wh.ultimo_intento_at = timezone.now()

    if entrega.intentos >= wh.MAX_INTENTOS:
        wh.estado = Webhook.ESTADO_ABANDONADO
        entrega.estado = WebhookEntrega.ESTADO_FALLIDO
    elif entrega.estado != WebhookEntrega.ESTADO_ENTREGADO:
        intento = min(self.request.retries, len(BACKOFF_BASE) - 1)
        countdown = backoff_con_jitter(intento)
        entrega.proximo_intento_at = timezone.now() + timezone.timedelta(
            seconds=countdown
        )
        entrega.estado = WebhookEntrega.ESTADO_REINTENTANDO

    wh.save(update_fields=["estado", "ultimo_intento_at", "ultimo_http_status"])
    entrega.save()

    if entrega.estado == WebhookEntrega.ESTADO_REINTENTANDO:
        intento = min(self.request.retries, len(BACKOFF_BASE) - 1)
        countdown = backoff_con_jitter(intento)
        raise self.retry(countdown=countdown)
