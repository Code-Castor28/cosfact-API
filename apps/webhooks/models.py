# ─── MODELS.PY — apps/webhooks/models.py ───
"""
apps/webhooks/models.py

Webhooks para notificar al cliente cuando cambia el estado de un comprobante.

SEGURIDAD:
- El secret del webhook se hashea (SHA-256) — nunca se guarda en texto plano.
- La URL DEBE ser HTTPS — validado en clean(), no solo en el serializer.
- Backoff exponencial en reintentos con límite MAX_INTENTOS.
- Payloads firmados con HMAC-SHA256 usando el secret original (que el cliente guarda).
"""
import hashlib
import secrets
import uuid
from django.db import models
from django.core.exceptions import ValidationError


MAX_INTENTOS = 5


class Webhook(models.Model):
    ESTADO_ACTIVO = "ACTIVO"
    ESTADO_FALLANDO = "FALLANDO"
    ESTADO_ABANDONADO = "ABANDONADO"
    ESTADO_INACTIVO = "INACTIVO"

    ESTADOS = [
        (ESTADO_ACTIVO, "Activo"),
        (ESTADO_FALLANDO, "Fallando (reintentos en progreso)"),
        (ESTADO_ABANDONADO, "Abandonado (máx. intentos alcanzado)"),
        (ESTADO_INACTIVO, "Inactivo (desactivado por el cliente)"),
    ]

    # Eventos disponibles para suscribirse
    EVENTO_COMPROBANTE_ACEPTADO = "comprobante.aceptado"
    EVENTO_COMPROBANTE_RECHAZADO = "comprobante.rechazado"
    EVENTO_COMPROBANTE_ANULADO = "comprobante.anulado"
    EVENTO_PAQUETE_AGOTADO = "paquete.agotado"
    EVENTO_CERTIFICADO_POR_VENCER = "certificado.por_vencer"

    EVENTOS_DISPONIBLES = [
        (EVENTO_COMPROBANTE_ACEPTADO, "Comprobante aceptado por DGII"),
        (EVENTO_COMPROBANTE_RECHAZADO, "Comprobante rechazado por DGII"),
        (EVENTO_COMPROBANTE_ANULADO, "Comprobante anulado"),
        (EVENTO_PAQUETE_AGOTADO, "Paquete de comprobantes agotado"),
        (EVENTO_CERTIFICADO_POR_VENCER, "Certificado próximo a vencer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.CASCADE,
        related_name="webhooks",
    )

    nombre = models.CharField(max_length=100)
    url = models.URLField(max_length=500)

    # SHA-256 del secret — el secret completo se muestra UNA VEZ al crear
    secret_hash = models.CharField(max_length=64, editable=False)

    # Eventos a los que está suscrito este webhook
    # Ej: ["comprobante.aceptado", "comprobante.rechazado"]
    eventos = models.JSONField(default=list)

    estado = models.CharField(max_length=15, choices=ESTADOS, default=ESTADO_ACTIVO)
    activo = models.BooleanField(default=True)

    ultimo_intento_at = models.DateTimeField(null=True, blank=True)
    ultimo_http_status = models.PositiveSmallIntegerField(null=True, blank=True)

    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "webhooks"
        verbose_name = "Webhook"
        verbose_name_plural = "Webhooks"
        indexes = [
            models.Index(fields=["empresa", "activo"]),
        ]

    def __str__(self):
        return f"{self.nombre} → {self.url} [{self.estado}]"

    # ─── Generación ──────────────────────────────────────────────────────────

    @classmethod
    def crear(cls, empresa, nombre, url, eventos):
        """
        Crea un webhook con secret generado automáticamente.
        Retorna (instancia, secret_completo).
        El secret_completo se muestra UNA SOLA VEZ al cliente.
        """
        secret = secrets.token_urlsafe(32)
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()

        instancia = cls(
            empresa=empresa,
            nombre=nombre,
            url=url,
            secret_hash=secret_hash,
            eventos=eventos,
        )
        instancia.full_clean()
        instancia.save()
        return instancia, secret

    # ─── Validaciones ─────────────────────────────────────────────────────────

    def clean(self):
        errores = {}

        # CORREGIDO: La URL DEBE ser HTTPS — validado en clean(), no solo en serializer
        if self.url and not self.url.startswith("https://"):
            errores["url"] = (
                "La URL del webhook debe usar HTTPS. "
                "Los payloads contienen datos fiscales sensibles."
            )

        # Validar que los eventos sean del conjunto permitido
        eventos_validos = {e[0] for e in self.EVENTOS_DISPONIBLES}
        if self.eventos:
            invalidos = [e for e in self.eventos if e not in eventos_validos]
            if invalidos:
                errores["eventos"] = f"Eventos inválidos: {', '.join(invalidos)}"

        if errores:
            raise ValidationError(errores)


class WebhookEntrega(models.Model):
    """Registro de cada intento de entrega de un evento."""

    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_ENTREGADO = "ENTREGADO"
    ESTADO_FALLIDO = "FALLIDO"
    ESTADO_REINTENTANDO = "REINTENTANDO"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_FALLIDO, "Fallido"),
        (ESTADO_REINTENTANDO, "Reintentando"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name="entregas",
    )

    comprobante = models.ForeignKey(
        "comprobantes.Comprobante",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="webhook_entregas",
    )

    evento = models.CharField(max_length=50)

    # SHA-256 del payload — para detectar si el contenido fue alterado
    payload_hash = models.CharField(max_length=64)

    estado = models.CharField(max_length=15, choices=ESTADOS, default=ESTADO_PENDIENTE)
    intentos = models.PositiveSmallIntegerField(default=0)
    max_intentos = models.PositiveSmallIntegerField(default=MAX_INTENTOS)
    ultimo_http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_mensaje = models.TextField(blank=True)

    proximo_intento_at = models.DateTimeField(null=True, blank=True)
    entregado_at = models.DateTimeField(null=True, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhook_entregas"
        verbose_name = "Entrega de Webhook"
        verbose_name_plural = "Entregas de Webhooks"
        indexes = [
            models.Index(fields=["webhook", "estado"]),
            models.Index(fields=["proximo_intento_at", "estado"]),
        ]

    def __str__(self):
        return f"{self.evento} → {self.webhook.url} [{self.estado}]"

    @property
    def puede_reintentar(self):
        return (
            self.estado in {self.ESTADO_FALLIDO, self.ESTADO_REINTENTANDO}
            and self.intentos < self.max_intentos
        )
