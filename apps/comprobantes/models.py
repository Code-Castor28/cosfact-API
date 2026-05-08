# ─── MODELS.PY — apps/comprobantes/models.py ───
"""
apps/comprobantes/models.py

Comprobantes electrónicos (e-CF) por empresa.

SEGURIDAD Y CUMPLIMIENTO:
- Inmutabilidad en save() Y en trigger de DB (el trigger está en la migración).
- ComprobanteDetalle también es inmutable cuando el padre está ACEPTADO.
- Todos los campos que la DGII requiere en el XML están presentes.
- xml_path usa namespacing por empresa: {empresa_uuid}/ecf/{año}/{encf}.xml
- idempotency_key para prevenir doble emisión por retry del POS.
- paquete_id FK registra exactamente qué paquete fue consumido.

ESTADOS:
  BORRADOR → PENDIENTE → PROCESANDO → ACEPTADO
                                    ↘ RECHAZADO → (corregir, re-emitir con nuevo e-NCF)
                    ANULADO (desde ACEPTADO, con nota de crédito)
                    ERROR (falla técnica, se puede reintentar)
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from sequences.models import TIPOS_ECF, TIPO_ECF_CHOICES


# Tipos que requieren comprobante de referencia (nota de crédito/débito)
TIPOS_REQUIEREN_REFERENCIA = {33, 34, 41}


class Comprobante(models.Model):
    # ─── Estados ──────────────────────────────────────────────────────────────
    ESTADO_BORRADOR = "BORRADOR"
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_PROCESANDO = "PROCESANDO"
    ESTADO_ACEPTADO = "ACEPTADO"
    ESTADO_RECHAZADO = "RECHAZADO"
    ESTADO_ANULADO = "ANULADO"
    ESTADO_ERROR = "ERROR"

    ESTADOS = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_PENDIENTE, "Pendiente de envío"),
        (ESTADO_PROCESANDO, "Procesando en DGII"),
        (ESTADO_ACEPTADO, "Aceptado por DGII"),
        (ESTADO_RECHAZADO, "Rechazado por DGII"),
        (ESTADO_ANULADO, "Anulado"),
        (ESTADO_ERROR, "Error técnico"),
    ]

    # Estados que hacen el comprobante inmutable
    ESTADOS_INMUTABLES = {ESTADO_ACEPTADO, ESTADO_ANULADO}

    # ─── Condición de pago ────────────────────────────────────────────────────
    CONDICION_CONTADO = "CONTADO"
    CONDICION_CREDITO = "CREDITO"
    CONDICION_LIBRE = "LIBRE"

    CONDICIONES_PAGO = [
        (CONDICION_CONTADO, "Contado"),
        (CONDICION_CREDITO, "Crédito"),
        (CONDICION_LIBRE, "Libre"),
    ]

    # ─── Campos ───────────────────────────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        related_name="comprobantes",
    )

    # Paquete consumido — registra exactamente qué paquete se usó
    paquete = models.ForeignKey(
        "subscriptions.PaqueteComprobantes",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="comprobantes",
    )

    # Prevención de doble emisión por retry del POS
    idempotency_key = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        help_text="UUID único por intento de emisión. El POS genera este valor.",
    )

    # ─── Datos DGII ───────────────────────────────────────────────────────────
    tipo_ecf = models.PositiveSmallIntegerField(choices=TIPO_ECF_CHOICES)
    encf = models.CharField(max_length=13, blank=True, db_index=True)  # E310000001

    # Emisor (la empresa — se llena automáticamente)
    rnc_emisor = models.CharField(max_length=11)

    # Receptor
    rnc_comprador = models.CharField(max_length=11, blank=True)
    cedula_comprador = models.CharField(max_length=11, blank=True)
    razon_social_comprador = models.CharField(max_length=255, blank=True)

    # Fecha y condiciones
    fecha_emision = models.DateTimeField(default=timezone.now)
    fecha_vencimiento_pago = models.DateField(null=True, blank=True)
    condicion_pago = models.CharField(
        max_length=10, choices=CONDICIONES_PAGO, default=CONDICION_CONTADO
    )

    # Montos (DGII requiere separar gravado e ITBIS)
    monto_gravado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_exento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_itbis = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Respuesta DGII
    estado = models.CharField(max_length=15, choices=ESTADOS, default=ESTADO_BORRADOR)
    track_id_dgii = models.CharField(max_length=255, blank=True)
    codigo_seguridad_dgii = models.CharField(max_length=255, blank=True)

    # URL de impresión e imagen QR (obligatorio en comprobante impreso)
    impresion_url = models.URLField(blank=True)
    qr_data = models.TextField(blank=True, help_text="Datos del QR para impresión.")

    # Referencia (obligatorio para notas de crédito/débito)
    comprobante_referencia = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="notas",
    )
    encf_referencia = models.CharField(
        max_length=13,
        blank=True,
        help_text="e-NCF del comprobante que se modifica con esta nota.",
    )

    # XML — path con namespacing por empresa para evitar colisiones
    # Formato: {empresa_uuid}/ecf/{año}/{encf}.xml
    xml_path = models.CharField(max_length=512, blank=True)
    xml_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 del XML firmado.")
    xml_version = models.CharField(
        max_length=10,
        blank=True,
        help_text="Versión del schema XML DGII usado para generar este comprobante.",
    )

    # Metadata
    intentos_envio = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.TextField(blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comprobantes"
        verbose_name = "Comprobante"
        verbose_name_plural = "Comprobantes"
        indexes = [
            models.Index(fields=["empresa", "estado"]),
            models.Index(fields=["empresa", "tipo_ecf"]),
            models.Index(fields=["encf"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["creado_at"]),
        ]

    def __str__(self):
        return f"{self.encf or '(sin e-NCF)'} — {self.empresa.rnc} [{self.estado}]"

    # ─── Inmutabilidad ────────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        """
        INMUTABILIDAD a nivel Python.
        CORREGIDO: También hay un trigger de DB en la migración para cubrir
        el caso de .update() que bypasea este save().
        """
        if self.pk:
            try:
                original = Comprobante.objects.values("estado").get(pk=self.pk)
                if original["estado"] in self.ESTADOS_INMUTABLES:
                    raise ValidationError(
                        f"No se puede modificar un comprobante en estado "
                        f"'{original['estado']}'. Es inmutable por cumplimiento fiscal."
                    )
            except Comprobante.DoesNotExist:
                pass

        # Auto-fill del RNC emisor
        if not self.rnc_emisor and self.empresa_id:
            self.rnc_emisor = self.empresa.rnc

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Nunca borrar comprobantes — retención legal 10 años."""
        raise ValidationError(
            "Los comprobantes no pueden eliminarse. Retención legal DGII: 10 años."
        )

    # ─── Validaciones ─────────────────────────────────────────────────────────

    def clean(self):
        errores = {}

        if self.tipo_ecf not in TIPOS_ECF:
            errores["tipo_ecf"] = f"Tipo e-CF inválido: {self.tipo_ecf}."

        # Notas de crédito/débito requieren referencia
        if self.tipo_ecf in TIPOS_REQUIEREN_REFERENCIA:
            if not self.encf_referencia and not self.comprobante_referencia_id:
                errores["encf_referencia"] = (
                    f"El tipo {self.tipo_ecf} requiere un comprobante de referencia."
                )

        # Validar montos básicos
        if self.monto_total < 0:
            errores["monto_total"] = "El monto total no puede ser negativo."

        calculado = self.monto_gravado + self.monto_exento + self.monto_itbis
        if abs(float(calculado) - float(self.monto_total)) > 0.01:
            errores["monto_total"] = (
                f"El monto total ({self.monto_total}) no coincide con "
                f"gravado + exento + ITBIS ({calculado})."
            )

        if errores:
            raise ValidationError(errores)

    # ─── Helpers de estado ────────────────────────────────────────────────────

    @property
    def es_inmutable(self):
        return self.estado in self.ESTADOS_INMUTABLES

    @property
    def puede_anularse(self):
        return self.estado == self.ESTADO_ACEPTADO

    @property
    def puede_reintentarse(self):
        return self.estado in {self.ESTADO_RECHAZADO, self.ESTADO_ERROR}


# ─────────────────────────────────────────────────────────────────────────────
# Detalle de Comprobante
# ─────────────────────────────────────────────────────────────────────────────

class ComprobanteDetalle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.PROTECT,   # PROTECT: no borrar detalles si el comprobante existe
        related_name="detalles",
    )

    numero_linea = models.PositiveSmallIntegerField()
    codigo_producto = models.CharField(max_length=50, blank=True)
    descripcion = models.CharField(max_length=500)
    cantidad = models.DecimalField(max_digits=14, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=4)
    descuento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    recargo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    itbis_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    itbis_monto = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "comprobante_detalles"
        verbose_name = "Detalle de Comprobante"
        verbose_name_plural = "Detalles de Comprobante"
        unique_together = [("comprobante", "numero_linea")]
        ordering = ["numero_linea"]

    def __str__(self):
        return f"Línea {self.numero_linea}: {self.descripcion}"

    def save(self, *args, **kwargs):
        """
        CORREGIDO: Los detalles también son inmutables cuando el padre está aceptado.
        """
        if self.comprobante_id:
            estado_padre = Comprobante.objects.values("estado").get(
                pk=self.comprobante_id
            )["estado"]
            if estado_padre in Comprobante.ESTADOS_INMUTABLES:
                raise ValidationError(
                    "No se pueden modificar los detalles de un comprobante "
                    f"en estado '{estado_padre}'."
                )
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Eventos del Comprobante (historial de cambios de estado)
# ─────────────────────────────────────────────────────────────────────────────

class ComprobanteEvento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.PROTECT,
        related_name="eventos",
    )

    estado_anterior = models.CharField(max_length=15, blank=True)
    estado_nuevo = models.CharField(max_length=15)
    mensaje = models.TextField(blank=True)
    datos_extra = models.JSONField(null=True, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comprobante_eventos"
        verbose_name = "Evento de Comprobante"
        verbose_name_plural = "Eventos de Comprobante"
        ordering = ["creado_at"]

    def __str__(self):
        return (
            f"{self.comprobante.encf}: "
            f"{self.estado_anterior} → {self.estado_nuevo}"
        )

    def save(self, *args, **kwargs):
        """Los eventos son inmutables — solo inserción."""
        if self.pk:
            raise ValidationError("Los eventos de comprobante no pueden modificarse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los eventos de comprobante no pueden eliminarse.")

