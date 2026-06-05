import hashlib
import json
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError
from empresas.models import Empresa
from .models import Webhook, WebhookEntrega
from .services import disparar_webhook, backoff_con_jitter


class WebhookModelTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )

    def test_crear_webhook_exitoso(self):
        wh, secret = Webhook.crear(
            empresa=self.empresa,
            nombre="Test Webhook",
            url="https://ejemplo.com/webhook",
            eventos=["comprobante.aceptado"],
        )
        self.assertEqual(wh.nombre, "Test Webhook")
        self.assertEqual(wh.url, "https://ejemplo.com/webhook")
        self.assertTrue(wh.activo)
        self.assertEqual(wh.estado, Webhook.ESTADO_ACTIVO)
        self.assertEqual(len(secret), 43)

    def test_crear_webhook_genera_secret_hash(self):
        wh, secret = Webhook.crear(
            empresa=self.empresa,
            nombre="Test",
            url="https://ejemplo.com/webhook",
            eventos=["comprobante.aceptado"],
        )
        expected_hash = hashlib.sha256(secret.encode()).hexdigest()
        self.assertEqual(wh.secret_hash, expected_hash)

    def test_clean_url_http_rechazado(self):
        wh = Webhook(
            empresa=self.empresa,
            nombre="HTTP Test",
            url="http://ejemplo.com/webhook",
        )
        with self.assertRaises(ValidationError) as ctx:
            wh.clean()
        self.assertIn("HTTPS", str(ctx.exception))

    def test_clean_evento_invalido_rechazado(self):
        wh = Webhook(
            empresa=self.empresa,
            nombre="Evento Inválido",
            url="https://ejemplo.com/webhook",
            eventos=["evento.invalido"],
        )
        with self.assertRaises(ValidationError) as ctx:
            wh.clean()
        self.assertIn("eventos", str(ctx.exception))

    def test_clean_eventos_validos_aceptados(self):
        wh = Webhook(
            empresa=self.empresa,
            nombre="Eventos Válidos",
            url="https://ejemplo.com/webhook",
            eventos=Webhook.EVENTOS_DISPONIBLES[0:2],
        )
        try:
            wh.clean()
        except ValidationError:
            self.fail("Eventos válidos lanzaron ValidationError")

    def test_crear_webhook_con_varios_eventos(self):
        wh, secret = Webhook.crear(
            empresa=self.empresa,
            nombre="Multi Evento",
            url="https://ejemplo.com/webhook",
            eventos=[
                "comprobante.aceptado",
                "comprobante.rechazado",
                "comprobante.anulado",
            ],
        )
        self.assertEqual(len(wh.eventos), 3)


class WebhookEntregaModelTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )
        self.webhook, self.secret = Webhook.crear(
            empresa=self.empresa,
            nombre="Test",
            url="https://ejemplo.com/webhook",
            eventos=["comprobante.aceptado"],
        )

    def test_crear_entrega(self):
        entrega = WebhookEntrega.objects.create(
            webhook=self.webhook,
            evento="comprobante.aceptado",
            payload_hash=hashlib.sha256(b"{}").hexdigest(),
        )
        self.assertEqual(entrega.estado, WebhookEntrega.ESTADO_PENDIENTE)
        self.assertEqual(entrega.intentos, 0)
        self.assertFalse(entrega.puede_reintentar)

    def test_entrega_fallida_puede_reintentar(self):
        entrega = WebhookEntrega.objects.create(
            webhook=self.webhook,
            evento="comprobante.aceptado",
            payload_hash=hashlib.sha256(b"{}").hexdigest(),
            estado=WebhookEntrega.ESTADO_FALLIDO,
            intentos=2,
        )
        self.assertTrue(entrega.puede_reintentar)

    def test_entrega_no_puede_reintentar_si_max_intentos(self):
        entrega = WebhookEntrega.objects.create(
            webhook=self.webhook,
            evento="comprobante.aceptado",
            payload_hash=hashlib.sha256(b"{}").hexdigest(),
            estado=WebhookEntrega.ESTADO_FALLIDO,
            intentos=5,
        )
        self.assertFalse(entrega.puede_reintentar)


class BackoffConJitterTest(TestCase):
    def test_backoff_primer_intento(self):
        resultado = backoff_con_jitter(0)
        self.assertGreaterEqual(resultado, 60)
        self.assertLess(resultado, 70)

    def test_backoff_ultimo_intento(self):
        resultado = backoff_con_jitter(4)
        self.assertGreaterEqual(resultado, 14400)
        self.assertLess(resultado, 15840)

    def test_backoff_fuera_de_rango(self):
        resultado = backoff_con_jitter(10)
        self.assertGreaterEqual(resultado, 14400)
        self.assertLess(resultado, 15840)


class DispararWebhookTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )

    @patch("webhooks.services.entregar_webhook.delay")
    def test_disparar_sin_webhooks_no_llama_nada(self, mock_delay):
        disparar_webhook(self.empresa, "comprobante.aceptado", {"key": "val"})
        mock_delay.assert_not_called()

    @patch("webhooks.services.entregar_webhook.delay")
    def test_disparar_webhook_activo_llama_delay(self, mock_delay):
        Webhook.crear(
            empresa=self.empresa,
            nombre="Test",
            url="https://ejemplo.com/webhook",
            eventos=["comprobante.aceptado"],
        )
        disparar_webhook(self.empresa, "comprobante.aceptado", {"key": "val"})
        mock_delay.assert_called_once()

    @patch("webhooks.services.entregar_webhook.delay")
    def test_disparar_solo_eventos_suscritos(self, mock_delay):
        Webhook.crear(
            empresa=self.empresa,
            nombre="Test",
            url="https://ejemplo.com/webhook",
            eventos=["comprobante.aceptado"],
        )
        disparar_webhook(self.empresa, "comprobante.rechazado", {"key": "val"})
        mock_delay.assert_not_called()

    @patch("webhooks.services.entregar_webhook.delay")
    def test_disparar_webhook_inactivo_no_llama(self, mock_delay):
        wh, _secret = Webhook.crear(
            empresa=self.empresa,
            nombre="Test",
            url="https://ejemplo.com/webhook",
            eventos=["comprobante.aceptado"],
        )
        wh.activo = False
        wh.save()
        disparar_webhook(self.empresa, "comprobante.aceptado", {"key": "val"})
        mock_delay.assert_not_called()
