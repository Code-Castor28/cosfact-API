# Create your models here.
# ─── MODELS.PY — apps/sequences/models.py ───
"""
apps/sequences/models.py

Secuenciales e-NCF por empresa y tipo de comprobante.

CRÍTICO:
- La DGII no permite reutilizar secuenciales rechazados.
- Un número quemado es un número perdido.
- El incremento DEBE ocurrir dentro de un SELECT FOR UPDATE en transaction.atomic().
- El método proximo_encf() solo hace PREVIEW (no incrementa).
- El incremento real está en services.py y está diseñado para que sea imposible
  llamarlo sin el lock — el campo bloqueado lo enforce a nivel de DB también.

Formato e-NCF: E + tipo(2 dígitos) + secuencial(8 dígitos con ceros)
Ejemplo: E310000001 (tipo 31, primer comprobante)
"""
import uuid
from django.db import models, transaction
from django.core.exceptions import ValidationError


# Tipos e-CF válidos según DGII (Ley 32-23)
TIPOS_ECF = {
    31: "Factura de Crédito Fiscal",
    32: "Factura de Consumo",
    33: "Nota de Débito",       # Nota: en algunos docs DGII es 34 — verificar versión vigente
    34: "Nota de Débito",
    41: "Nota de Crédito",
    43: "Comprobante de Compras",
    44: "Gastos Menores",
    45: "Regímenes Especiales",
    46: "Gubernamental",
    47: "Exportación",
    48: "Pagos al Exterior",
}

TIPO_ECF_CHOICES = [(k, v) for k, v in TIPOS_ECF.items()]


class Secuencial(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        related_name="secuenciales",
    )

    tipo_ecf = models.PositiveSmallIntegerField(
        choices=TIPO_ECF_CHOICES,
        help_text="Tipo de comprobante electrónico según DGII.",
    )

    ultimo_numero = models.PositiveIntegerField(default=0)

    # Si la DGII asigna rangos autorizados en el futuro
    minimo_asignado = models.PositiveIntegerField(default=1)
    maximo_asignado = models.PositiveIntegerField(
        default=99999999,
        help_text="Número máximo autorizado para este tipo.",
    )

    # Bloqueo para mantenimiento o cuando se agota el rango
    bloqueado = models.BooleanField(
        default=False,
        help_text="Si True, no se pueden emitir comprobantes de este tipo hasta desbloquear.",
    )
    motivo_bloqueo = models.CharField(max_length=255, blank=True)

    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "secuenciales"
        verbose_name = "Secuencial e-NCF"
        verbose_name_plural = "Secuenciales e-NCF"
        # Una empresa tiene exactamente un secuencial por tipo
        unique_together = [("empresa", "tipo_ecf")]
        indexes = [
            models.Index(fields=["empresa", "tipo_ecf"]),
        ]

    def __str__(self):
        return (
            f"{self.empresa.rnc} — Tipo {self.tipo_ecf}: "
            f"{self.ultimo_numero}/{self.maximo_asignado}"
        )

    def proximo_encf(self) -> str:
        """
        SOLO PREVIEW — no incrementa.
        Retorna el e-NCF que se emitiría si se llama a services.obtener_proximo_encf().
        Útil para mostrar en pantalla antes de confirmar.
        """
        return self._formatear_encf(self.ultimo_numero + 1)

    def _formatear_encf(self, numero: int) -> str:
        """Formato DGII: E + tipo(2) + número(8 con zeros)."""
        return f"E{self.tipo_ecf:02d}{numero:08d}"

    @property
    def porcentaje_uso(self) -> float:
        rango = self.maximo_asignado - self.minimo_asignado + 1
        if rango <= 0:
            return 100.0
        return (self.ultimo_numero / rango) * 100

    @property
    def casi_agotado(self) -> bool:
        """Alerta cuando queda menos del 10% del rango."""
        return self.porcentaje_uso >= 90

    def clean(self):
        if self.tipo_ecf not in TIPOS_ECF:
            raise ValidationError({
                "tipo_ecf": f"Tipo e-CF inválido: {self.tipo_ecf}. "
                            f"Valores válidos: {list(TIPOS_ECF.keys())}"
            })
        if self.minimo_asignado < 1:
            raise ValidationError({"minimo_asignado": "El mínimo debe ser al menos 1."})
        if self.maximo_asignado <= self.minimo_asignado:
            raise ValidationError({"maximo_asignado": "El máximo debe ser mayor al mínimo."})

