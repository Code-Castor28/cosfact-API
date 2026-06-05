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
# Fuente: https://dgii.gov.do/cicloContribuyente/facturacion/comprobantesFiscalesElectronicosE-CF/Paginas/TipoyEstructurae-CF.aspx
TIPOS_ECF = {
    31: "Factura de Crédito Fiscal",
    32: "Factura de Consumo",
    33: "Nota de Débito",
    34: "Nota de Crédito",
    41: "Comprobante de Compras",
    43: "Gastos Menores",
    44: "Regímenes Especiales",
    45: "Gubernamental",
    46: "Exportación",
    47: "Pagos al Exterior",
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
        default=9999999999,
        help_text="Número máximo autorizado para este tipo.",
    )

    # Bloqueo para mantenimiento o cuando se agota el rango
    bloqueado = models.BooleanField(
        default=False,
        help_text="Si True, no se pueden emitir comprobantes de este tipo hasta desbloquear.",
    )
    motivo_bloqueo = models.CharField(max_length=255, blank=True)

    fecha_bloqueo = models.DateTimeField(# type: ignore[call-type]
        null=True, blank=True,
        help_text="Momento en que se bloqueó el secuencial."
    )
    usuario_bloqueo = models.ForeignKey(
        "users.Usuario",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="secuenciales_bloqueados",
        help_text="Usuario que realizó el bloqueo.",
    )

    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "secuenciales"
        verbose_name = "Secuencial e-NCF"
        verbose_name_plural = "Secuenciales e-NCF"
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "tipo_ecf"],
                name="uq_secuencial_empresa_tipoecf",
            ),
            models.CheckConstraint(
                check=models.Q(minimo_asignado__gte=1),
                name="ck_secuencial_minimo_asignado",
            ),
            models.CheckConstraint(
                check=models.Q(
                    maximo_asignado__gt=models.F("minimo_asignado")),
                name="ck_secuencial_maximo_mayor_minimo",
            ),
            models.CheckConstraint(
                check=models.Q(ultimo_numero__gte=0),
                name="ck_secuencial_ultimo_numero",
            ),
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
        """Formato DGII: E + tipo(2) + número(10 con zeros)."""
        return f"E{self.tipo_ecf:02d}{numero:010d}"

    @property
    def porcentaje_uso(self) -> float:
        rango = self.maximo_asignado - self.minimo_asignado + 1
        if rango <= 0:
            return 100.0
        utilizados = self.ultimo_numero - self.minimo_asignado + 1
        if utilizados < 0:
            return 0.0
        return (utilizados / rango) * 100

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
            raise ValidationError(
                {"minimo_asignado": "El mínimo debe ser al menos 1."})
        if self.maximo_asignado <= self.minimo_asignado:
            raise ValidationError(
                {"maximo_asignado": "El máximo debe ser mayor al mínimo."})
        if self.ultimo_numero > self.maximo_asignado:
            raise ValidationError(
                {"ultimo_numero": "El último número no puede exceder el máximo asignado."})


class NumeroViciado(models.Model):
    """Registro inmutable de e-NCF que no pueden reutilizarse tras un rechazo DGII."""
    empresa = models.ForeignKey(
        "empresas.Empresa", on_delete=models.PROTECT
    )
    encf = models.CharField(max_length=13)
    motivo = models.TextField()
    viciado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "numeros_viciados"
        verbose_name = "Número Viciado"
        verbose_name_plural = "Números Viciados"
        unique_together = [("empresa", "encf")]

    def __str__(self):
        return f"{self.encf} — {self.empresa.rnc}"


class MovimientoSecuencial(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    secuencial = models.ForeignKey(
        Secuencial,
        on_delete=models.PROTECT,
        related_name="movimientos",
    )

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        related_name="movimientos_secuenciales",
    )

    tipo_ecf = models.PositiveSmallIntegerField(
        choices=TIPO_ECF_CHOICES,
    )

    numero_asignado = models.PositiveIntegerField(
        help_text="Número secuencial asignado.",
    )

    encf_generado = models.CharField(
        max_length=13,
        help_text="e-NCF completo generado (E + tipo + número).",
    )

    comprobante = models.ForeignKey(
        "comprobantes.Comprobante",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="movimientos_secuenciales",
        help_text="Comprobante al que se asignó este e-NCF.",
    )

    usuario = models.ForeignKey(
        "users.Usuario",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="movimientos_secuenciales",
        help_text="Usuario que realizó la operación.",
    )

    creado_at = models.DateTimeField(auto_now_add=True) # type: ignore[call-arg]

    class Meta:
        db_table = "movimientos_secuenciales"
        verbose_name = "Movimiento de Secuencial"
        verbose_name_plural = "Movimientos de Secuenciales"
        ordering = ["-creado_at"]
        indexes = [
            models.Index(fields=["empresa", "tipo_ecf", "creado_at"]),
            models.Index(fields=["comprobante"]),
        ]

    def __str__(self):
        return f"{self.encf_generado} — {self.creado_at}"
