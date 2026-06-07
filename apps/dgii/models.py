# ─── MODELS.PY — apps/dgii/models.py ───
"""
apps/dgii/models.py

Logs de comunicación con la DGII.

SEGURIDAD:
- request_xml y response_xml SE GUARDAN CIFRADOS en producción
  (el XML de autenticación contiene semilla firmada; el e-CF contiene datos fiscales).
- Para logs de autenticación, implementar purga automática a los 90 días.
- Para logs de comprobantes, retención 10 años (cumplimiento DGII).
- xml_version registra el schema usado para cada operación.
"""
import uuid
from django.core.exceptions import ValidationError
from django.db import models


class DGIILog(models.Model):
    TIPO_AUTENTICACION = "AUTENTICACION"
    TIPO_ENVIO = "ENVIO_ECF"
    TIPO_CONSULTA = "CONSULTA_ESTADO"
    TIPO_ANULACION = "ANULACION"
    TIPO_SEMILLA = "OBTENER_SEMILLA"

    TIPOS = [
        (TIPO_AUTENTICACION, "Autenticación (ValidarSemilla)"),
        (TIPO_ENVIO, "Envío de e-CF"),
        (TIPO_CONSULTA, "Consulta de estado"),
        (TIPO_ANULACION, "Anulación"),
        (TIPO_SEMILLA, "Obtener semilla"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        related_name="dgii_logs",
    )

    comprobante = models.ForeignKey(
        "comprobantes.Comprobante",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dgii_logs",
    )

    ambiente = models.CharField(
        max_length=20,
        choices=[
            ("testecf", "Test"),
            ("certecf", "Certificación"),
            ("ecf", "Producción"),
        ],
    )

    tipo_operacion = models.CharField(max_length=20, choices=TIPOS)
    endpoint = models.CharField(max_length=255, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)

    # XML cifrado con Fernet (igual que tokens DGII)
    # Usar empresas.crypto.cifrar() / descifrar()
    request_xml_cifrado = models.TextField(blank=True)
    response_xml_cifrado = models.TextField(blank=True)

    # Schema DGII usado en esta operación
    xml_version = models.CharField(max_length=10, blank=True)

    codigo_error = models.CharField(max_length=50, blank=True)
    mensaje = models.TextField(blank=True)
    exitoso = models.BooleanField(default=False)
    duracion_ms = models.PositiveIntegerField(null=True, blank=True)

    # ─── Campos nuevos Fase DGII ──────────────────────────────────────────
    estado_respuesta = models.CharField(
        max_length=20, blank=True,
        choices=[
            ("ACEPTADO", "Aceptado"),
            ("RECHAZADO", "Rechazado"),
            ("PENDIENTE", "Pendiente"),
            ("TIMEOUT", "Timeout"),
            ("ERROR_RED", "Error de red"),
        ],
    )
    codigo_dgii = models.CharField(max_length=50, blank=True)
    mensaje_dgii = models.TextField(blank=True)
    respuesta_raw = models.JSONField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)

    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dgii_logs"
        verbose_name = "Log DGII"
        verbose_name_plural = "Logs DGII"
        indexes = [
            models.Index(fields=["empresa", "tipo_operacion", "creado_at"]),
            models.Index(fields=["empresa", "creado_at"]),
            models.Index(fields=["comprobante"]),
            models.Index(fields=["exitoso", "creado_at"]),
        ]

    def __str__(self):
        return (
            f"{self.empresa.rnc} — {self.tipo_operacion} "
            f"[{self.http_status}] {self.creado_at:%Y-%m-%d %H:%M}"
        )

    def save(self, *args, **kwargs):
        """Los logs son append-only. No se modifican."""
        if self.pk:
            raise ValidationError(
                "Los registros de auditoría no pueden modificarse."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los registros de auditoría no pueden eliminarse. Retención legal 10 años.")


# ─── Catálogos DGII ─────────────────────────────────────────────────────────
from .catalogs.models import Provincia, Municipio, UnidadMedida, Moneda, ImpuestoAdicional, FormaPago  # noqa: F401, E501
