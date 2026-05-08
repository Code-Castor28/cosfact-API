# Create your models here.
# ─── MODELS.PY — apps/empresas/models.py ───
"""
apps/empresas/models.py
Tenants del SaaS. Cada empresa es un cliente.
SEGURIDAD CRÍTICA:
- El certificado .p12 NUNCA se guarda localmente. Solo se guarda una storage_key
  que apunta al archivo en almacenamiento externo (MinIO / DigitalOcean Spaces).
- El PIN del certificado NUNCA toca la base de datos. Viaja cifrado en el request
  y se pasa directamente al proceso de firma en memoria.
- El token DGII se guarda cifrado (Fernet AES-128-CBC) en la DB.
  La FERNET_KEY vive en variables de entorno del VPS.
"""
import uuid
from django.db import models
from django.utils import timezone


class EmpresaManager(models.Manager):
    """
    Manager base. Siempre filtrar activas por defecto.
    Para multi-tenant usar EmpresaQuerySet.for_empresa(empresa) en vistas.
    """
    def get_queryset(self):
        return super().get_queryset()

    def activas(self):
        return self.get_queryset().filter(activa=True)


class Empresa(models.Model):
    AMBIENTE_TEST = "testecf"
    AMBIENTE_CERT = "certecf"
    AMBIENTE_PROD = "ecf"

    AMBIENTES = [
        (AMBIENTE_TEST, "Desarrollo / Test"),
        (AMBIENTE_CERT, "Certificación"),
        (AMBIENTE_PROD, "Producción"),
    ]

    ESTADO_ACTIVA = "ACTIVA"
    ESTADO_SUSPENDIDA = "SUSPENDIDA"
    ESTADO_CANCELADA = "CANCELADA"
    ESTADO_PENDIENTE = "PENDIENTE_CERTIFICADO"

    ESTADOS = [
        (ESTADO_ACTIVA, "Activa"),
        (ESTADO_SUSPENDIDA, "Suspendida"),
        (ESTADO_CANCELADA, "Cancelada"),
        (ESTADO_PENDIENTE, "Pendiente de Certificado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Datos DGII
    rnc = models.CharField(max_length=11, unique=True)
    razon_social = models.CharField(max_length=255)
    nombre_comercial = models.CharField(max_length=255, blank=True)

    # Configuración DGII
    ambiente = models.CharField(max_length=20, choices=AMBIENTES, default=AMBIENTE_TEST)
    estado = models.CharField(max_length=30, choices=ESTADOS, default=ESTADO_PENDIENTE)
    activa = models.BooleanField(default=True)

    # Certificado digital .p12 — NUNCA guardar el archivo aquí
    # storage_key es la referencia al objeto en MinIO/S3: "{uuid}/certs/certificado.p12"
    certificado_storage_key = models.CharField(max_length=512, blank=True)
    # SHA-256 del archivo .p12 para verificar integridad en cada carga
    certificado_hash = models.CharField(max_length=64, blank=True)
    certificado_vence_at = models.DateField(null=True, blank=True)

    # Soft delete — nunca borrar por cumplimiento legal 10 años
    deleted_at = models.DateTimeField(null=True, blank=True)

    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    objects = EmpresaManager()

    class Meta:
        db_table = "empresas"
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        indexes = [
            models.Index(fields=["rnc"]),
            models.Index(fields=["estado", "activa"]),
        ]

    def __str__(self):
        return f"{self.razon_social} ({self.rnc})"

    def delete(self, *args, **kwargs):
        """Soft delete. Nunca borrar por retención legal obligatoria (10 años DGII)."""
        self.deleted_at = timezone.now()
        self.activa = False
        self.save(update_fields=["deleted_at", "activa"])

    @property
    def certificado_vence_pronto(self):
        """Alerta si el certificado vence en los próximos 30 días."""
        if not self.certificado_vence_at:
            return False
        return (self.certificado_vence_at - timezone.now().date()).days <= 30

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.rnc and len(self.rnc.replace("-", "")) not in (9, 11):
            raise ValidationError({"rnc": "El RNC debe tener 9 u 11 dígitos."})


class TokenDGII(models.Model):
    """
    Caché del token de sesión DGII por empresa y ambiente.
    SEGURIDAD: El token se guarda CIFRADO con Fernet (AES-128-CBC + HMAC-SHA256).
    La clave Fernet (FERNET_KEY) debe estar en variables de entorno del servidor,
    nunca en el código ni en la DB.
    Para cifrar/descifrar usar apps.empresas.crypto.cifrar_token / descifrar_token
    """
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="tokens_dgii",
    )
    ambiente = models.CharField(max_length=20, choices=Empresa.AMBIENTES)

    # Token cifrado con Fernet — en texto plano se vería basura base64
    token_cifrado = models.TextField()

    expedido_at = models.DateTimeField()
    expira_at = models.DateTimeField()
    activo = models.BooleanField(default=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tokens_dgii"
        verbose_name = "Token DGII"
        verbose_name_plural = "Tokens DGII"
        # Una empresa solo tiene un token activo por ambiente
        unique_together = [("empresa", "ambiente", "activo")]
        indexes = [
            models.Index(fields=["empresa", "ambiente", "activo"]),
            models.Index(fields=["expira_at"]),
        ]

    def __str__(self):
        return f"Token {self.empresa.rnc} [{self.ambiente}] - {'Activo' if self.activo else 'Expirado'}"

    @property
    def esta_vigente(self):
        return self.activo and timezone.now() < self.expira_at

    def invalidar(self):
        self.activo = False
        self.save(update_fields=["activo"])