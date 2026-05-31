import uuid
from typing import Any, ClassVar
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class Pago(models.Model):
    METODO_EFECTIVO: ClassVar[str] = "EFECTIVO"
    METODO_TRANSFERENCIA: ClassVar[str] = "TRANSFERENCIA"
    METODO_DEPOSITO: ClassVar[str] = "DEPOSITO"
    METODO_CHEQUE: ClassVar[str] = "CHEQUE"
    METODO_OTRO: ClassVar[str] = "OTRO"

    METODOS_PAGO: ClassVar[list[tuple[str, str]]] = [
        ("EFECTIVO", "Efectivo"),
        ("TRANSFERENCIA", "Transferencia"),
        ("DEPOSITO", "Depósito"),
        ("CHEQUE", "Cheque"),
        ("OTRO", "Otro"),
    ]

    ESTADO_PENDIENTE: ClassVar[str] = "PENDIENTE"
    ESTADO_CONFIRMADO: ClassVar[str] = "CONFIRMADO"
    ESTADO_RECHAZADO: ClassVar[str] = "RECHAZADO"

    ESTADOS: ClassVar[list[tuple[str, str]]] = [
        ("PENDIENTE", "Pendiente"),
        ("CONFIRMADO", "Confirmado"),
        ("RECHAZADO", "Rechazado"),
    ]

    MONEDA_DOP: ClassVar[str] = "DOP"
    MONEDA_USD: ClassVar[str] = "USD"

    MONEDAS: ClassVar[list[tuple[str, str]]] = [
        ("DOP", "Peso Dominicano"),
        ("USD", "Dólar Estadounidense"),
    ]

    TIPO_RENOVACION: ClassVar[str] = "RENOVACION"
    TIPO_ADICIONAL: ClassVar[str] = "ADICIONAL"

    TIPOS_PAGO: ClassVar[list[tuple[str, str]]] = [
        ("RENOVACION", "Renovación de Suscripción"),
        ("ADICIONAL", "Paquete Adicional"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        related_name="pagos",
    )
    suscripcion = models.ForeignKey(
        "subscriptions.Suscripcion",
        on_delete=models.PROTECT,
        related_name="pagos",
    )
    plan = models.ForeignKey(
        "subscriptions.Plan",
        on_delete=models.PROTECT,
        related_name="pagos",
    )

    monto = models.DecimalField(max_digits=10, decimal_places=2)
    moneda = models.CharField(
        max_length=10, choices=MONEDAS, default=MONEDA_DOP)
    tipo_pago = models.CharField(
        max_length=20, choices=TIPOS_PAGO, default=TIPO_RENOVACION)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, blank=True)
    referencia = models.CharField(max_length=100, blank=True)
    fecha_pago = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_PENDIENTE,
    )
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_confirmados",
    )
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)

    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    def clean(self) -> None:
        """
        Validaciones personalizadas:
        1. Si metodo_pago != EFECTIVO, referencia es requerida.
        2. No puede haber otro pago PENDIENTE de RENOVACION para el mismo cliente.
        """
        # Validación 1: Referencia obligatoria para métodos no-EFECTIVO
        referencia: str = self.referencia or ""
        if (
            self.metodo_pago
            and self.metodo_pago != self.METODO_EFECTIVO
            and not referencia.strip()
        ):
            raise ValidationError({
                'referencia': f'Requerida para pagos por {self.metodo_pago}'
            })

        # Validación 2: No adelantos (sin múltiples PENDIENTES para renovaciones)
        es_nuevo: bool = self._state.adding
        if self.estado == self.ESTADO_PENDIENTE and self.tipo_pago == self.TIPO_RENOVACION and es_nuevo:
            existe_pendiente = Pago.objects.filter(
                empresa=self.empresa,
                estado=self.ESTADO_PENDIENTE,
                tipo_pago=self.TIPO_RENOVACION,
            ).exists()

            if existe_pendiente:
                raise ValidationError({
                    'empresa': 'Ya existe una renovación PENDIENTE para esta empresa. '
                               'No se permiten adelantos simultáneos.'
                })

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Llamar clean() antes de guardar."""
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "pagos"
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-creado_at"]
        indexes = [
            models.Index(fields=["empresa", "estado"]),
            models.Index(fields=["estado", "creado_at"]),
        ]

    def __str__(self) -> str:
        empresa_rnc: str = self.empresa.rnc  # type: ignore[attr-defined]
        return f"{empresa_rnc} - {self.monto} {self.moneda} [{self.estado}]"


class HistorialPago(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        related_name="historial_pagos",
    )
    suscripcion = models.ForeignKey(
        "subscriptions.Suscripcion",
        on_delete=models.PROTECT,
        related_name="historial_pagos",
    )
    plan = models.ForeignKey(
        "subscriptions.Plan",
        on_delete=models.PROTECT,
        related_name="historial_pagos",
    )
    pago = models.OneToOneField(
        Pago,
        on_delete=models.PROTECT,
        related_name="historial",
    )
    paquete = models.ForeignKey(
        "subscriptions.PaqueteComprobantes",
        on_delete=models.PROTECT,
        related_name="historial_pagos",
    )

    periodo_mes = models.PositiveSmallIntegerField()
    periodo_ano = models.PositiveSmallIntegerField()
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2)
    comprobantes_asignados = models.PositiveIntegerField()

    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "historial_pagos"
        verbose_name = "Historial de Pago"
        verbose_name_plural = "Historial de Pagos"
        ordering = ["-periodo_ano", "-periodo_mes"]
        indexes = [
            models.Index(fields=["empresa", "periodo_ano", "periodo_mes"]),
            models.Index(fields=["suscripcion"]),
        ]

    def __str__(self) -> str:
        empresa_rnc: str = self.empresa.rnc  # type: ignore[attr-defined]
        return f"{empresa_rnc} - {self.periodo_mes}/{self.periodo_ano}"
