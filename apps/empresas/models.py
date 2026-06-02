# ─── MODELS.PY — apps/empresas/models.py ───
"""
apps/empresas/models.py
Tenants del SaaS. Cada empresa es un cliente.
SEGURIDAD CRÍTICA:
- El PIN del certificado .p12 se cifra con Fernet (CRYPTOGRAPHY_MASTER_KEY)
  y se almacena en CertificadoDigital.pin_cifrado.
- El PIN solo se descifra en memoria durante la firma y se descarta inmediatamente.
- El archivo .p12 se guarda via FileField en CertificadoDigital.archivo.
- El token DGII se guarda cifrado (Fernet AES-128-CBC) en TokenDGII.token_cifrado.
- La FERNET_KEY / CRYPTOGRAPHY_MASTER_KEY vive en variables de entorno del VPS.
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

    # Datos de contacto
    correo = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.TextField(blank=True)

    # Certificado digital .p12 — NUNCA guardar el archivo aquí
    # storage_key es la referencia al objeto en MinIO/S3: "{uuid}/certs/certificado.p12"
    certificado_storage_key = models.CharField(max_length=512, blank=True)
    # SHA-256 del archivo .p12 para verificar integridad en cada carga
    certificado_hash = models.CharField(max_length=64, blank=True)
    certificado_vence_at = models.DateField(null=True, blank=True)

    # Onboarding — deuda pendiente impide nuevas emisiones
    onboarding_bloqueado = models.BooleanField(default=False)

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
    def is_authenticated(self):
        """Permite usar Empresa como request.user en DRF (Api-Key auth)."""
        return True

    # Seguridad: rol=None para que user.rol no lance AttributeError
    # cuando una Empresa se usa como request.user (Api-Key auth).
    # Así, permisos como IsSuperAdmin fallan gracefully en vez de crash.
    rol = None

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
    Para cifrar/descifrar usar empresas.crypto.cifrar / descifrar
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


class CertificadoDigital(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="certificados",
    )
    alias = models.CharField(max_length=100, help_text="Nombre descriptivo del certificado")
    archivo = models.FileField(
        upload_to="certificados/",
        help_text="Archivo .p12 del certificado digital",
    )
    pin_cifrado = models.TextField(
        help_text="PIN del certificado cifrado con Fernet (CRYPTOGRAPHY_MASTER_KEY)",
    )
    vigencia_desde = models.DateField()
    vigencia_hasta = models.DateField()
    activo = models.BooleanField(
        default=True,
        help_text="Solo un certificado activo por empresa",
    )
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "certificados_digitales"
        verbose_name = "Certificado Digital"
        verbose_name_plural = "Certificados Digitales"

    def __str__(self):
        return f"{self.alias} — {self.empresa.rnc} {'(activo)' if self.activo else ''}"
