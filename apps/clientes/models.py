import uuid
from django.db import models
from django.core.exceptions import ValidationError


class Cliente(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.CASCADE,
        related_name="clientes",
    )
    rnc_cedula = models.CharField(max_length=11, db_index=True)
    razon_social = models.CharField(max_length=150)
    direccion = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clientes"
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        unique_together = [("empresa", "rnc_cedula")]
        ordering = ["-creado_at"]

    def __str__(self):
        return f"{self.razon_social} ({self.rnc_cedula})"

    def clean(self):
        if self.rnc_cedula:
            if not self.rnc_cedula.isdigit() or len(self.rnc_cedula) != 11:
                raise ValidationError(
                    {"rnc_cedula": "RNC/Cédula debe tener exactamente 11 dígitos numéricos."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
