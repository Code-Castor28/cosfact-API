# Create your models here.
# ─── MODELS.PY — apps/subscriptions/models.py ───
"""
apps/subscriptions/models.py

Lógica de planes, suscripciones y paquetes de comprobantes.

REGLAS DE NEGOCIO:
- Los comprobantes no se acumulan entre paquetes.
- Si el cliente consume todo el paquete, debe comprar otro.
- Si no lo consume, los sobrantes no pasan al siguiente período.
- El consumo usa SELECT FOR UPDATE para evitar race conditions.
- Un cliente puede tener múltiples paquetes comprados; se consume en orden FIFO.
"""
import uuid
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator


# ─────────────────────────────────────────────
# Plan
# ─────────────────────────────────────────────
class Plan(models.Model):
    CICLO_MENSUAL = "MENSUAL"
    CICLO_ANUAL = "ANUAL"
    CICLO_AMBOS = "AMBOS"

    CICLOS = [
        (CICLO_MENSUAL, "Solo Mensual"),
        (CICLO_ANUAL, "Solo Anual"),
        (CICLO_AMBOS, "Mensual y Anual"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    limite_comprobantes = models.PositiveIntegerField(
        help_text="Cantidad de comprobantes incluidos en este plan."
    )

    precio_mensual = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    precio_anual = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # CORREGIDO: max_length en lugar de max_digits (que es de DecimalField)
    ciclo_disponible = models.CharField(
        max_length=10,
        choices=CICLOS,
        default=CICLO_AMBOS,
    )

    dias_gracia = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(15)],
        help_text="Días de gracia después de la fecha de renovación (0-15)."
    )

    # JSON: lista de tipos e-CF permitidos, ej: [31, 32, 41]
    # null = todos los tipos permitidos
    tipos_ecf_permitidos = models.JSONField(
        null=True,
        blank=True,
        help_text="Lista de tipos e-CF permitidos. null = todos.",
    )

    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0, help_text="Orden de display en el portal.")
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planes"
        verbose_name = "Plan"
        verbose_name_plural = "Planes"
        ordering = ["orden", "limite_comprobantes"]

    def __str__(self):
        return f"{self.nombre} ({self.limite_comprobantes} comprobantes)"

    def clean(self):
        if self.ciclo_disponible in (self.CICLO_MENSUAL, self.CICLO_AMBOS) and not self.precio_mensual:
            raise ValidationError({"precio_mensual": "El precio mensual es requerido para este ciclo."})
        if self.ciclo_disponible in (self.CICLO_ANUAL, self.CICLO_AMBOS) and not self.precio_anual:
            raise ValidationError({"precio_anual": "El precio anual es requerido para este ciclo."})


# ─────────────────────────────────────────────
# Suscripción
# ─────────────────────────────────────────────
class Suscripcion(models.Model):
    CICLO_MENSUAL = "MENSUAL"
    CICLO_ANUAL = "ANUAL"

    CICLOS = [
        (CICLO_MENSUAL, "Mensual"),
        (CICLO_ANUAL, "Anual"),
    ]

    ESTADO_ACTIVA = "ACTIVA"
    ESTADO_SUSPENDIDA = "SUSPENDIDA"
    ESTADO_CANCELADA = "CANCELADA"
    ESTADO_VENCIDA = "VENCIDA"

    ESTADOS = [
        (ESTADO_ACTIVA, "Activa"),
        (ESTADO_SUSPENDIDA, "Suspendida"),
        (ESTADO_CANCELADA, "Cancelada"),
        (ESTADO_VENCIDA, "Vencida"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        related_name="suscripciones",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="suscripciones",
    )

    ciclo = models.CharField(max_length=10, choices=CICLOS)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_ACTIVA)

    fecha_inicio = models.DateField()
    fecha_renovacion = models.DateField()

    # Precio que pagó al momento de contratar (puede cambiar el plan, el precio histórico queda aquí)
    precio_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "suscripciones"
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"
        indexes = [
            models.Index(fields=["empresa", "estado"]),
            models.Index(fields=["fecha_renovacion"]),
        ]

    def __str__(self):
        return f"{self.empresa.rnc} — {self.plan.nombre} [{self.ciclo}]"

    @property
    def esta_activa(self):
        if self.estado != self.ESTADO_ACTIVA:
            return False
        
        fecha_renovacion = self.fecha_renovacion
        if fecha_renovacion >= timezone.now().date():
            return True
        
        dias_gracia = getattr(self.plan, 'dias_gracia', 0) or 0
        if dias_gracia == 0:
            return False
        
        fecha_limite_gracia = fecha_renovacion + timedelta(days=dias_gracia)
        return timezone.now().date() <= fecha_limite_gracia


# ─────────────────────────────────────────────
# Paquete de Comprobantes
# ─────────────────────────────────────────────
class PaqueteComprobantes(models.Model):
    ESTADO_ACTIVO = "ACTIVO"
    ESTADO_AGOTADO = "AGOTADO"
    ESTADO_VENCIDO = "VENCIDO"
    ESTADO_CANCELADO = "CANCELADO"

    ESTADOS = [
        (ESTADO_ACTIVO, "Activo"),
        (ESTADO_AGOTADO, "Agotado"),
        (ESTADO_VENCIDO, "Vencido"),
        (ESTADO_CANCELADO, "Cancelado"),
    ]

    ORIGEN_SUSCRIPCION = "SUSCRIPCION"
    ORIGEN_ADICIONAL = "COMPRA_ADICIONAL"

    ORIGENES = [
        (ORIGEN_SUSCRIPCION, "Generado por suscripción"),
        (ORIGEN_ADICIONAL, "Compra adicional"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        related_name="paquetes",
    )
    suscripcion = models.ForeignKey(
        Suscripcion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="paquetes",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="paquetes",
    )

    total_comprobantes = models.PositiveIntegerField()
    comprobantes_usados = models.PositiveIntegerField(default=0)

    estado = models.CharField(max_length=15, choices=ESTADOS, default=ESTADO_ACTIVO)
    origen = models.CharField(max_length=20, choices=ORIGENES, default=ORIGEN_SUSCRIPCION)

    fecha_compra = models.DateTimeField(auto_now_add=True)
    # null = no vence (por diseño del negocio)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)

    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "paquetes_comprobantes"
        verbose_name = "Paquete de Comprobantes"
        verbose_name_plural = "Paquetes de Comprobantes"
        indexes = [
            models.Index(fields=["empresa", "estado"]),
            models.Index(fields=["fecha_vencimiento"]),
        ]
        # FIFO: consumir primero el paquete más antiguo activo
        ordering = ["fecha_compra"]

    def __str__(self):
        return f"{self.empresa.rnc} — {self.comprobantes_usados}/{self.total_comprobantes}"

    @property
    def comprobantes_restantes(self):
        """Calculado, no columna — evita inconsistencias."""
        return max(0, self.total_comprobantes - self.comprobantes_usados)

    @property
    def disponible(self):
        if self.estado != self.ESTADO_ACTIVO:
            return False
        
        if self.fecha_vencimiento and timezone.now() > self.fecha_vencimiento:
            dias_gracia = 0
            if self.suscripcion:
                dias_gracia = getattr(self.suscripcion.plan, 'dias_gracia', 0) or 0
                if dias_gracia > 0:
                    fecha_limite = self.fecha_vencimiento + timedelta(days=dias_gracia)
                    if timezone.now() > fecha_limite:
                        return False
                else:
                    return False
            else:
                return False
        
        return self.comprobantes_restantes > 0

    def clean(self):
        if self.plan and self.total_comprobantes > self.plan.limite_comprobantes:
            raise ValidationError({
                "total_comprobantes": (
                    f"El plan '{self.plan.nombre}' solo permite "
                    f"{self.plan.limite_comprobantes} comprobantes."
                )
            })
        
        if self.suscripcion and self.fecha_vencimiento:
            fecha_inicio = self.suscripcion.fecha_inicio or timezone.now().date()
            ciclo = self.suscripcion.ciclo
            
            if ciclo == Suscripcion.CICLO_MENSUAL:
                max_fecha = fecha_inicio + relativedelta(months=1)
                if self.fecha_vencimiento.date() > max_fecha:
                    raise ValidationError({
                        "fecha_vencimiento": (
                            f"Ciclo MENSUAL. La fecha de vencimiento no puede "
                            f"exceder 1 mes ({max_fecha})."
                        )
                    })
            elif ciclo == Suscripcion.CICLO_ANUAL:
                max_fecha = fecha_inicio + relativedelta(years=1)
                if self.fecha_vencimiento.date() > max_fecha:
                    raise ValidationError({
                        "fecha_vencimiento": (
                            f"Ciclo ANUAL. La fecha de vencimiento no puede "
                            f"exceder 1 año ({max_fecha})."
                        )
                    })

    def consumir_comprobante(self) -> bool:
        """
        Consume 1 comprobante de este paquete de forma atómica.

        RACE CONDITION RESUELTO:
        - El SELECT FOR UPDATE ocurre AQUÍ, no delegado al servicio.
        - Usar siempre dentro de un atomic() block.
        - Retorna True si consumió, False si el paquete está agotado/vencido.

        Uso correcto:
            with transaction.atomic():
                paquete = PaqueteComprobantes.objects.select_for_update().get(id=paquete_id)
                if not paquete.consumir_comprobante():
                    raise InsufficientQuotaError(...)
        """
        if not self.disponible:
            return False

        self.comprobantes_usados += 1

        if self.comprobantes_restantes == 0:
            self.estado = self.ESTADO_AGOTADO

        self.save(update_fields=["comprobantes_usados", "estado"])
        return True

    def revertir_consumo(self):
        """
        Revierte un consumo (por ejemplo si el comprobante fue RECHAZADO por la DGII).
        También atómico — llamar dentro de transaction.atomic() con select_for_update().
        """
        if self.comprobantes_usados > 0:
            self.comprobantes_usados -= 1
            if self.estado == self.ESTADO_AGOTADO:
                self.estado = self.ESTADO_ACTIVO
            self.save(update_fields=["comprobantes_usados", "estado"])
