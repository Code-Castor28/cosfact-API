import uuid
from django.db import models
from django.conf import settings


class Pago(models.Model):
    METODO_EFECTIVO = "EFECTIVO"
    METODO_TRANSFERENCIA = "TRANSFERENCIA"
    METODO_DEPOSITO = "DEPOSITO"
    METODO_CHEQUE = "CHEQUE"
    METODO_OTRO = "OTRO"

    METODOS_PAGO = [
        (METODO_EFECTIVO, "Efectivo"),
        (METODO_TRANSFERENCIA, "Transferencia"),
        (METODO_DEPOSITO, "Depósito"),
        (METODO_CHEQUE, "Cheque"),
        (METODO_OTRO, "Otro"),
    ]

    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_CONFIRMADO = "CONFIRMADO"
    ESTADO_RECHAZADO = "RECHAZADO"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_CONFIRMADO, "Confirmado"),
        (ESTADO_RECHAZADO, "Rechazado"),
    ]

    MONEDA_DOP = "DOP"
    MONEDA_USD = "USD"

    MONEDAS = [
        (MONEDA_DOP, "Peso Dominicano"),
        (MONEDA_USD, "Dólar Estadounidense"),
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
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO)
    referencia = models.CharField(max_length=100, blank=True)
    fecha_pago = models.DateTimeField()
    fecha_corte = models.PositiveSmallIntegerField(
        help_text="Día fijo del mes (1-28)"
    )
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

    def clean(self):
        """
        Validaciones personalizadas:
        1. Si metodo_pago != EFECTIVO, referencia es requerida
        2. No puede haber otro pago PENDIENTE para el mismo cliente (no adelantos)
        """
        from django.core.exceptions import ValidationError

        # Validación 1: Referencia obligatoria para métodos no-EFECTIVO
        if (self.metodo_pago and
            self.metodo_pago != self.METODO_EFECTIVO and
                not self.referencia.strip()):
            raise ValidationError({
                'referencia': f'Requerida para pagos por {self.metodo_pago}'
            })

        # Validación 2: No adelantos (no múltiples PENDIENTES simultáneamente)
        # Al crear (sin pk)
        if self.estado == self.ESTADO_PENDIENTE and not self.pk:
            existe_pendiente = Pago.objects.filter(
                empresa=self.empresa,
                estado=self.ESTADO_PENDIENTE,
            ).exclude(pk=self.pk).exists()

            if existe_pendiente:
                raise ValidationError({
                    'empresa': 'Ya existe un pago PENDIENTE para esta empresa. '
                               'No se permiten adelantos simultáneos.'
                })

    def save(self, *args, **kwargs):
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

    def __str__(self):
        return f"{self.empresa.rnc} - {self.monto} {self.moneda} [{self.estado}]"


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
        unique_together = [["empresa", "periodo_mes", "periodo_ano"]]

    def __str__(self):
        return f"{self.empresa.rnc} - {self.periodo_mes}/{self.periodo_ano}"
