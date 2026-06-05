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
                    ERROR (falla técnica)
                    CONTINGENCIA (reintento automático cuando DGII falla)
"""
import uuid
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from sequences.models import TIPOS_ECF, TIPO_ECF_CHOICES

# Tipos e-CF habilitados en Fase 1 (MVP)
TIPOS_FASE_1 = {31, 32, 33, 34, 41}


class Comprobante(models.Model):
    # ─── Estados ──────────────────────────────────────────────────────────────
    ESTADO_BORRADOR = "BORRADOR"
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_PROCESANDO = "PROCESANDO"
    ESTADO_ACEPTADO = "ACEPTADO"
    ESTADO_RECHAZADO = "RECHAZADO"
    ESTADO_ANULADO = "ANULADO"
    ESTADO_ERROR = "ERROR"
    ESTADO_CONTINGENCIA = "CONTINGENCIA"

    ESTADOS = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_PENDIENTE, "Pendiente de envío"),
        (ESTADO_PROCESANDO, "Procesando en DGII"),
        (ESTADO_ACEPTADO, "Aceptado por DGII"),
        (ESTADO_RECHAZADO, "Rechazado por DGII"),
        (ESTADO_ANULADO, "Anulado"),
        (ESTADO_ERROR, "Error técnico"),
        (ESTADO_CONTINGENCIA, "Contingencia"),
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
    # El POS envía este UUID en el header Idempotency-Key
    idempotency_key = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        help_text="UUID único por intento de emisión. Enviado por el POS en header Idempotency-Key.",
    )

    # ─── Datos DGII ───────────────────────────────────────────────────────────
    tipo_ecf = models.PositiveSmallIntegerField(choices=TIPO_ECF_CHOICES)
    encf = models.CharField(max_length=13, blank=True, db_index=True)  # E310000001

    # Emisor (la empresa — se llena automáticamente)
    rnc_emisor = models.CharField(max_length=11)

    # Receptor
    rnc_comprador = models.CharField(max_length=11, blank=True, null=True)
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
    monto_impuesto_adicional = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    monto_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_avance_pago = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    saldo_anterior = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    valor_pagar = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    indicador_monto_gravado = models.PositiveSmallIntegerField(
        choices=[(0, "Monto sin ITBIS"), (1, "Monto con ITBIS incluido")],
        default=0,
    )

    # Respuesta DGII
    estado = models.CharField(max_length=15, choices=ESTADOS, default=ESTADO_BORRADOR)
    track_id_dgii = models.CharField(max_length=255, blank=True)
    codigo_seguridad_dgii = models.CharField(max_length=255, blank=True)

    # URL de impresión e imagen QR (obligatorio en comprobante impreso)
    impresion_url = models.URLField(blank=True)
    qr_data = models.TextField(blank=True, help_text="Datos del QR para impresión.")

    # Referencia (FK opcional — solo analítica, no obligatorio)
    comprobante_referencia = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas",
    )
    ncf_modificado = models.CharField(
        max_length=13,
        blank=True,
        help_text="e-NCF del comprobante que se modifica con esta nota (E33/E34).",
    )

    # --- Nuevos campos planos ---
    direccion_comprador = models.CharField(max_length=255, blank=True)

    # FK a catálogo de clientes (analítica)
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comprobantes",
    )

    # Montos
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Notas / Observaciones
    observaciones = models.TextField(blank=True)

    # Certificado usado para firmar
    certificado_usado = models.ForeignKey(
        "empresas.CertificadoDigital",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comprobantes",
    )

    # Campos para Notas E33/E34
    codigo_modificacion = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[
            (1, "Anulación"),
            (2, "Texto"),
            (3, "Montos"),
            (4, "Contingencia"),
            (5, "Referencia E32"),
        ],
    )
    razon_modificacion = models.CharField(max_length=90, blank=True)

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

    # ─── Máquina de estados ────────────────────────────────────────────────────

    TRANSICIONES_PERMITIDAS = {
        "BORRADOR":    {"PENDIENTE"},
        "PENDIENTE":   {"PROCESANDO"},
        "PROCESANDO":  {"ACEPTADO", "RECHAZADO", "ERROR", "CONTINGENCIA"},
        "ACEPTADO":    {"ANULADO"},
        "RECHAZADO":   {"BORRADOR"},
        "ERROR":       {"PENDIENTE"},
        "CONTINGENCIA":{"PENDIENTE"},
        "ANULADO":     set(),
    }

    # ─── Inmutabilidad ────────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        """
        INMUTABILIDAD a nivel Python + validación de máquina de estados.
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
                if self.estado != original["estado"]:
                    if self.estado not in self.TRANSICIONES_PERMITIDAS.get(
                            original["estado"], set()):
                        raise ValidationError(
                            f"Transición inválida: "
                            f"{original['estado']} -> {self.estado}"
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

        # 1. Rechazar tipos fuera de Fase 1 (MVP)
        if self.tipo_ecf not in TIPOS_FASE_1:
            raise ValidationError(
                {"tipo_ecf": f"Tipo e-CF {self.tipo_ecf} no soportado en Fase 1. "
                             f"Tipos válidos: 31, 32, 33, 34, 41."}
            )

        # 2. E31 (Crédito Fiscal): RNC + Razón Social obligatorios
        if self.tipo_ecf == 31:
            if not self.rnc_comprador:
                errores["rnc_comprador"] = "E31 requiere RNC/Cédula del comprador."
            if not self.razon_social_comprador:
                errores["razon_social_comprador"] = "E31 requiere Razón Social del comprador."

        # 3. E32 (Consumo): Regla del umbral RD$250,000
        if self.tipo_ecf == 32:
            monto_total = self.monto_total or Decimal("0.00")
            if monto_total >= Decimal("250000.00"):
                if not self.rnc_comprador and not self.cedula_comprador:
                    errores["rnc_comprador"] = (
                        "E32 >= RD$250,000 requiere RNC/Cédula del comprador."
                    )
            elif not self.rnc_comprador:
                self.razon_social_comprador = "CONSUMIDOR FINAL"

        # 4. E33/E34 (Notas): Validación de campos de referencia
        if self.tipo_ecf in (33, 34):
            if not self.ncf_modificado:
                errores["ncf_modificado"] = f"E{self.tipo_ecf} requiere el e-NCF del comprobante modificado."
            if not self.codigo_modificacion:
                errores["codigo_modificacion"] = f"E{self.tipo_ecf} requiere código de modificación (1-5)."
            if not self.razon_modificacion:
                errores["razon_modificacion"] = f"E{self.tipo_ecf} requiere razón de la modificación."

            if self.ncf_modificado:
                original = Comprobante.objects.filter(
                    encf=self.ncf_modificado,
                    estado=Comprobante.ESTADO_ACEPTADO,
                ).first()
                if not original:
                    errores["ncf_modificado"] = (
                        f"El e-NCF {self.ncf_modificado} no existe o no está ACEPTADO."
                    )
                else:
                    if self.rnc_comprador and original.rnc_comprador:
                        if self.rnc_comprador != original.rnc_comprador:
                            errores["rnc_comprador"] = (
                                "El RCN del comprador de la nota debe coincidir "
                                "con el RNC de la factura original."
                            )
                    if self.tipo_ecf == 34:
                        if self.monto_total and original.monto_total:
                            if self.monto_total > original.monto_total:
                                errores["monto_total"] = (
                                    "Nota de Crédito E34 no puede superar el "
                                    f"monto del e-CF original ({original.monto_total})."
                                )

            if self.razon_modificacion:
                self.razon_modificacion = self.razon_modificacion[:90]

        # 5. Validación de consistencia de montos
        calculado = self.monto_gravado + self.monto_exento + self.monto_itbis
        if self.monto_total and abs(calculado - self.monto_total) > Decimal("0.01"):
            errores["monto_total"] = (
                f"Monto total ({self.monto_total}) no coincide con "
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
        return self.estado == self.ESTADO_BORRADOR

    @property
    def puede_reintentarse(self):
        return self.estado in {
            self.ESTADO_RECHAZADO,
            self.ESTADO_ERROR,
            self.ESTADO_CONTINGENCIA,
        }


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

    # DGII §6 — Campos del ItemComprobante
    indicador_facturacion = models.PositiveSmallIntegerField(
        choices=[
            (1, "Bienes o servicios gravados con ITBIS 18%"),
            (2, "Bienes o servicios gravados con ITBIS 16%"),
            (3, "Bienes o servicios gravados con ITBIS 0%"),
            (4, "Bienes o servicios exentos"),
        ],
        default=1,
    )
    nombre_item = models.CharField(max_length=200, default="")
    unidad_medida = models.PositiveSmallIntegerField(default=1)
    cantidad = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    precio_unitario_item = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    descuento_monto = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_item = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Campos legacy — mantenidos por compatibilidad
    codigo_producto = models.CharField(max_length=50, blank=True)
    descripcion = models.CharField(max_length=500, blank=True)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    descuento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    recargo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    itbis_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    itbis_monto = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)

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

