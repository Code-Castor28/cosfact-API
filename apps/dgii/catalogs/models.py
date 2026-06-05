from django.db import models


class Provincia(models.Model):
    codigo = models.CharField(max_length=6, primary_key=True)
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = "dgii_provincias"
        verbose_name = "Provincia"
        verbose_name_plural = "Provincias"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class Municipio(models.Model):
    codigo = models.CharField(max_length=6, primary_key=True)
    provincia = models.ForeignKey(
        Provincia, on_delete=models.CASCADE, related_name="municipios"
    )
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = "dgii_municipios"
        verbose_name = "Municipio"
        verbose_name_plural = "Municipios"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class UnidadMedida(models.Model):
    codigo = models.PositiveSmallIntegerField(primary_key=True)
    abreviatura = models.CharField(max_length=10)
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = "dgii_unidades_medida"
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.abreviatura} — {self.nombre}"


class Moneda(models.Model):
    codigo_iso = models.CharField(max_length=3, primary_key=True)
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = "dgii_monedas"
        verbose_name = "Moneda"
        verbose_name_plural = "Monedas"
        ordering = ["codigo_iso"]

    def __str__(self):
        return f"{self.codigo_iso} — {self.nombre}"


class ImpuestoAdicional(models.Model):
    codigo = models.CharField(max_length=3, primary_key=True)
    nombre = models.CharField(max_length=100, blank=True)
    descripcion = models.CharField(max_length=200, blank=True)
    tipo = models.CharField(
        max_length=20,
        choices=[
            ("PORCENTUAL", "Porcentual"),
            ("ESPECIFICO", "Específico (Monto Fijo)"),
            ("ADVALOREM", "Ad Valorem (Porcentual)"),
        ],
        default="PORCENTUAL",
    )
    tasa = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "dgii_impuestos_adicionales"
        verbose_name = "Impuesto Adicional"
        verbose_name_plural = "Impuestos Adicionales"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre or self.descripcion} ({self.tasa}%)"


class FormaPago(models.Model):
    codigo = models.PositiveSmallIntegerField(primary_key=True)
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = "dgii_formas_pago"
        verbose_name = "Forma de Pago"
        verbose_name_plural = "Formas de Pago"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"
