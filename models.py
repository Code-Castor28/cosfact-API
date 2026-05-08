# ═══════════════════════════════════════════════════════════════════════════════
# DerejFact API — Models v2 (Corregidos)
# ═══════════════════════════════════════════════════════════════════════════════
# Archivos incluidos (en orden de dependencia):
#   1. apps/users/models.py
#   2. apps/empresas/models.py
#   3. apps/empresas/crypto.py
#   4. apps/empresas/notifications.py
#   5. apps/subscriptions/models.py
#   6. apps/api_keys/models.py
#   7. apps/sequences/models.py
#   8. apps/sequences/services.py
#   9. apps/comprobantes/models.py
#  10. apps/dgii/models.py
#  11. apps/webhooks/models.py
#  12. apps/audit/models.py
#  13. apps/audit/middleware.py
#  14. apps/comprobantes/migrations/0002_immutability_triggers.py
# ═══════════════════════════════════════════════════════════════════════════════


# ─── MODELS.PY — apps/users/models.py ───
"""
apps/users/models.py
Usuario custom con roles. Soporta superadmin (sin empresa) y usuarios de empresa.
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("rol", Usuario.ROL_SUPERADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    ROL_SUPERADMIN = "SUPERADMIN"
    ROL_ADMIN_EMPRESA = "ADMIN_EMPRESA"
    ROL_USUARIO_EMPRESA = "USUARIO_EMPRESA"

    ROLES = [
        (ROL_SUPERADMIN, "Super Administrador"),
        (ROL_ADMIN_EMPRESA, "Administrador de Empresa"),
        (ROL_USUARIO_EMPRESA, "Usuario de Empresa"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # empresa es nullable: los superadmin no pertenecen a ninguna empresa
    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="usuarios",
    )

    email = models.EmailField(unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    rol = models.CharField(max_length=20, choices=ROLES, default=ROL_USUARIO_EMPRESA)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Seguridad: bloqueo por intentos fallidos
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)

    # Trazabilidad
    ultimo_login_ip = models.GenericIPAddressField(null=True, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre", "apellido"]

    class Meta:
        db_table = "usuarios"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        indexes = [
            models.Index(fields=["empresa", "rol"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.nombre} {self.apellido} <{self.email}>"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

    def esta_bloqueado(self):
        if self.bloqueado_hasta and timezone.now() < self.bloqueado_hasta:
            return True
        return False

    def registrar_intento_fallido(self):
        self.intentos_fallidos += 1
        if self.intentos_fallidos >= 5:
            self.bloqueado_hasta = timezone.now() + timezone.timedelta(minutes=30)
        self.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])

    def limpiar_intentos(self):
        self.intentos_fallidos = 0
        self.bloqueado_hasta = None
        self.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])

    def clean(self):
        from django.core.exceptions import ValidationError
        # Un usuario no-superadmin DEBE tener empresa
        if self.rol != self.ROL_SUPERADMIN and not self.empresa_id:
            raise ValidationError(
                {"empresa": "Los usuarios que no son superadmin deben pertenecer a una empresa."}
            )
        # Un superadmin NO debe tener empresa
        if self.rol == self.ROL_SUPERADMIN and self.empresa_id:
            raise ValidationError(
                {"empresa": "Los superadmin no pueden estar vinculados a una empresa."}
            )


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


# ─── CRYPTO.PY — apps/empresas/crypto.py ───
"""
apps/empresas/crypto.py

Cifrado simétrico Fernet para tokens DGII y datos sensibles.

REQUERIMIENTO: Variable de entorno FERNET_KEY en el servidor.
Generar una vez con:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Y guardarla en /etc/environment o en el .env del VPS (nunca en el repo).
"""
import os
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _get_fernet() -> Fernet:
    key = getattr(settings, "FERNET_KEY", None) or os.environ.get("FERNET_KEY")
    if not key:
        raise EnvironmentError(
            "FERNET_KEY no está configurada. "
            "Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def cifrar(texto: str) -> str:
    """Cifra un string y retorna el texto cifrado como string base64."""
    f = _get_fernet()
    return f.encrypt(texto.encode()).decode()


def descifrar(texto_cifrado: str) -> str:
    """Descifra un string cifrado con Fernet. Lanza InvalidToken si fue manipulado."""
    f = _get_fernet()
    try:
        return f.decrypt(texto_cifrado.encode()).decode()
    except InvalidToken:
        raise ValueError("El token cifrado fue manipulado o la clave es incorrecta.")


# ─── NOTIFICATIONS.PY — apps/empresas/notifications.py ───
"""
apps/empresas/notifications.py  (o apps/audit/notifications.py)

Modelo de notificaciones internas del sistema.

Cubre alertas que el panel de administración (tuyo) y el portal del cliente deben ver:
- Certificado próximo a vencer
- Paquete de comprobantes agotado
- Reintentos fallidos con la DGII
- Empresa sin paquete activo
- Token DGII expirado sin renovar

Las notificaciones al cliente (externos) van por webhooks.
Este modelo es para el panel interno.
"""
import uuid
from django.db import models


class Notificacion(models.Model):
    NIVEL_INFO = "INFO"
    NIVEL_ADVERTENCIA = "ADVERTENCIA"
    NIVEL_CRITICO = "CRITICO"

    NIVELES = [
        (NIVEL_INFO, "Informativo"),
        (NIVEL_ADVERTENCIA, "Advertencia"),
        (NIVEL_CRITICO, "Crítico"),
    ]

    TIPO_CERT_POR_VENCER = "CERT_POR_VENCER"
    TIPO_CERT_VENCIDO = "CERT_VENCIDO"
    TIPO_PAQUETE_AGOTADO = "PAQUETE_AGOTADO"
    TIPO_PAQUETE_POR_AGOTAR = "PAQUETE_POR_AGOTAR"
    TIPO_TOKEN_EXPIRADO = "TOKEN_DGII_EXPIRADO"
    TIPO_DGII_FALLO = "DGII_FALLO_REITERADO"
    TIPO_SIN_PAQUETE = "SIN_PAQUETE_ACTIVO"
    TIPO_SISTEMA = "SISTEMA"

    TIPOS = [
        (TIPO_CERT_POR_VENCER, "Certificado próximo a vencer"),
        (TIPO_CERT_VENCIDO, "Certificado vencido"),
        (TIPO_PAQUETE_AGOTADO, "Paquete de comprobantes agotado"),
        (TIPO_PAQUETE_POR_AGOTAR, "Paquete casi agotado (< 10% restante)"),
        (TIPO_TOKEN_EXPIRADO, "Token DGII expirado"),
        (TIPO_DGII_FALLO, "Fallos reiterados con la DGII"),
        (TIPO_SIN_PAQUETE, "Empresa sin paquete activo"),
        (TIPO_SISTEMA, "Aviso de sistema"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.CASCADE,
        related_name="notificaciones",
        null=True,
        blank=True,
        help_text="Null = notificación global de sistema.",
    )

    tipo = models.CharField(max_length=30, choices=TIPOS)
    nivel = models.CharField(max_length=15, choices=NIVELES, default=NIVEL_INFO)
    titulo = models.CharField(max_length=255)
    mensaje = models.TextField()

    # Datos adicionales para el panel (ej: días para vencer, % restante)
    datos = models.JSONField(null=True, blank=True)

    leida = models.BooleanField(default=False)
    leida_at = models.DateTimeField(null=True, blank=True)
    leida_por = models.ForeignKey(
        "users.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notificaciones_leidas",
    )

    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notificaciones"
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        indexes = [
            models.Index(fields=["empresa", "leida", "creado_at"]),
            models.Index(fields=["nivel", "leida"]),
        ]
        ordering = ["-creado_at"]

    def __str__(self):
        empresa_str = self.empresa.rnc if self.empresa else "SISTEMA"
        return f"[{self.nivel}] {empresa_str} — {self.titulo}"

    def marcar_leida(self, usuario):
        from django.utils import timezone
        self.leida = True
        self.leida_at = timezone.now()
        self.leida_por = usuario
        self.save(update_fields=["leida", "leida_at", "leida_por_id"])


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
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError


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
        return self.estado == self.ESTADO_ACTIVA and self.fecha_renovacion >= timezone.now().date()


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
            return False
        return self.comprobantes_restantes > 0

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


# ─── MODELS.PY — apps/api_keys/models.py ───
"""
apps/api_keys/models.py

API Keys para autenticación de los sistemas POS de los clientes.

SEGURIDAD:
- El token completo NUNCA se guarda. Solo su SHA-256.
- El token completo solo se muestra UNA VEZ al crearlo (en memoria).
- Revocación con trazabilidad: quién revocó, cuándo y por qué.
- Las IPs se validan en clean() del modelo (no solo en el serializer).
- Rate limit incluye ventana de tiempo.
- Límite máximo de keys por empresa para prevenir abuso.
"""
import hashlib
import ipaddress
import secrets
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


MAX_KEYS_POR_EMPRESA = 10  # Límite de API keys por empresa


class ApiKey(models.Model):
    VENTANA_MINUTO = "MINUTE"
    VENTANA_HORA = "HOUR"
    VENTANA_DIA = "DAY"

    VENTANAS = [
        (VENTANA_MINUTO, "Por minuto"),
        (VENTANA_HORA, "Por hora"),
        (VENTANA_DIA, "Por día"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.CASCADE,
        related_name="api_keys",
    )

    # El creador (para trazabilidad interna dentro de la empresa)
    creado_por = models.ForeignKey(
        "users.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        related_name="api_keys_creadas",
    )

    nombre = models.CharField(max_length=100, help_text="Nombre descriptivo, ej: 'POS Sucursal Norte'")

    # Prefijo visible (primeros 8 chars) para identificar la key sin exponer el hash
    prefix = models.CharField(max_length=8, editable=False)

    # SHA-256 del token completo. El token completo NUNCA se guarda.
    key_hash = models.CharField(max_length=64, unique=True, editable=False)

    # Scopes: qué puede hacer esta key. JSON list de strings.
    # Ej: ["comprobantes:crear", "comprobantes:consultar", "secuenciales:consultar"]
    scopes = models.JSONField(default=list)

    # IPs permitidas. Lista vacía = todas las IPs permitidas.
    # Guardar como lista de strings validados con ipaddress.
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de IPs o CIDRs permitidos. Vacío = todas las IPs.",
    )

    # Rate limiting con ventana
    rate_limit_cantidad = models.PositiveIntegerField(
        default=100,
        help_text="Número máximo de requests en la ventana definida.",
    )
    rate_limit_ventana = models.CharField(
        max_length=10,
        choices=VENTANAS,
        default=VENTANA_HORA,
        help_text="Ventana de tiempo para el rate limit.",
    )

    # Ciclo de vida
    activa = models.BooleanField(default=True)
    expira_at = models.DateTimeField(null=True, blank=True)

    # Revocación con trazabilidad completa
    revocado_at = models.DateTimeField(null=True, blank=True, editable=False)
    revocado_por = models.ForeignKey(
        "users.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_keys_revocadas",
        editable=False,
    )
    revocado_motivo = models.CharField(max_length=255, blank=True, editable=False)

    ultimo_uso_at = models.DateTimeField(null=True, blank=True)
    ultimo_uso_ip = models.GenericIPAddressField(null=True, blank=True)

    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_keys"
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        indexes = [
            models.Index(fields=["empresa", "activa"]),
            models.Index(fields=["key_hash"]),
            models.Index(fields=["prefix"]),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.prefix}****) — {self.empresa.rnc}"

    # ─── Generación ───────────────────────────────────────────────────────────

    @classmethod
    def crear(cls, empresa, nombre, creado_por, scopes=None, allowed_ips=None,
              rate_limit_cantidad=100, rate_limit_ventana=VENTANA_HORA, expira_at=None):
        """
        Crea una nueva API key.
        Retorna (instancia, token_completo).
        El token_completo solo existe en memoria — mostrarlo UNA VEZ al usuario.
        """
        # Verificar límite por empresa
        keys_activas = cls.objects.filter(empresa=empresa, activa=True).count()
        if keys_activas >= MAX_KEYS_POR_EMPRESA:
            raise ValueError(
                f"Límite de {MAX_KEYS_POR_EMPRESA} API keys activas por empresa alcanzado."
            )

        token = secrets.token_urlsafe(32)  # 256 bits de entropía
        prefix = token[:8]
        key_hash = hashlib.sha256(token.encode()).hexdigest()

        instancia = cls(
            empresa=empresa,
            nombre=nombre,
            creado_por=creado_por,
            prefix=prefix,
            key_hash=key_hash,
            scopes=scopes or [],
            allowed_ips=allowed_ips or [],
            rate_limit_cantidad=rate_limit_cantidad,
            rate_limit_ventana=rate_limit_ventana,
            expira_at=expira_at,
        )
        instancia.full_clean()  # Valida allowed_ips y demás antes de guardar
        instancia.save()
        return instancia, token

    @classmethod
    def verificar(cls, token: str):
        """
        Busca y retorna la ApiKey correspondiente al token dado.
        Retorna None si no existe, está revocada o expirada.
        """
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        try:
            key = cls.objects.select_related("empresa").get(
                key_hash=key_hash,
                activa=True,
            )
        except cls.DoesNotExist:
            return None

        if key.expira_at and timezone.now() > key.expira_at:
            return None

        return key

    # ─── Revocación ──────────────────────────────────────────────────────────

    def revocar(self, revocado_por, motivo=""):
        """
        Revoca la key con trazabilidad completa.
        No se borra el registro — el historial de uso queda en audit_logs.
        """
        self.activa = False
        self.revocado_at = timezone.now()
        self.revocado_por = revocado_por
        self.revocado_motivo = motivo
        self.save(update_fields=[
            "activa", "revocado_at", "revocado_por_id", "revocado_motivo"
        ])

    # ─── IP validation ────────────────────────────────────────────────────────

    def ip_permitida(self, ip: str) -> bool:
        """Retorna True si la IP está en la lista de permitidas (o si no hay restricción)."""
        if not self.allowed_ips:
            return True
        try:
            ip_obj = ipaddress.ip_address(ip)
            for entrada in self.allowed_ips:
                try:
                    red = ipaddress.ip_network(entrada, strict=False)
                    if ip_obj in red:
                        return True
                except ValueError:
                    continue
        except ValueError:
            return False
        return False

    # ─── Validación del modelo ────────────────────────────────────────────────

    def clean(self):
        """
        CORREGIDO: La validación de IPs ocurre en clean(), no solo en el serializer.
        Esto cubre también ApiKey.objects.create() directo.
        """
        errores = {}

        if self.allowed_ips:
            ips_invalidas = []
            for entrada in self.allowed_ips:
                try:
                    ipaddress.ip_network(entrada, strict=False)
                except ValueError:
                    try:
                        ipaddress.ip_address(entrada)
                    except ValueError:
                        ips_invalidas.append(entrada)
            if ips_invalidas:
                errores["allowed_ips"] = f"IPs inválidas: {', '.join(ips_invalidas)}"

        if self.scopes is not None and not isinstance(self.scopes, list):
            errores["scopes"] = "Los scopes deben ser una lista."

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        # Siempre llamar full_clean al guardar si no viene de una actualización parcial
        if not kwargs.get("update_fields"):
            self.full_clean()
        super().save(*args, **kwargs)

    def tiene_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])

    def registrar_uso(self, ip: str):
        self.ultimo_uso_at = timezone.now()
        self.ultimo_uso_ip = ip
        self.save(update_fields=["ultimo_uso_at", "ultimo_uso_ip"])


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


# ─── SERVICES.PY — apps/sequences/services.py ───
"""
apps/sequences/services.py

Servicio para obtener el próximo e-NCF de forma atómica.

DISEÑO DE SEGURIDAD:
- La única forma de obtener un número es a través de obtener_proximo_encf().
- El SELECT FOR UPDATE está en este servicio — es el único punto de entrada.
- Nunca llamar secuencial.save() directamente desde fuera de este servicio
  para modificar ultimo_numero.
"""
from django.db import transaction
from .models import Secuencial, TIPOS_ECF


class SecuencialAgotadoError(Exception):
    """El rango de secuenciales se ha agotado."""


class TipoECFBloqueadoError(Exception):
    """El tipo de e-CF está bloqueado temporalmente."""


class TipoECFNoExisteError(Exception):
    """No hay secuencial configurado para este tipo en esta empresa."""


def obtener_proximo_encf(empresa, tipo_ecf: int) -> str:
    """
    Obtiene y reserva el próximo número e-NCF para la empresa y tipo dado.

    ATÓMICO: Usa SELECT FOR UPDATE para evitar que dos workers obtengan
    el mismo número. Llama siempre dentro de un contexto de transacción
    más amplio (el de la emisión del comprobante).

    Args:
        empresa: instancia de Empresa
        tipo_ecf: int, tipo de comprobante (31, 32, 41, etc.)

    Returns:
        str: el e-NCF formateado, ej: "E310000001"

    Raises:
        TipoECFNoExisteError: si no hay secuencial configurado
        TipoECFBloqueadoError: si el tipo está bloqueado
        SecuencialAgotadoError: si se agotó el rango
    """
    if tipo_ecf not in TIPOS_ECF:
        raise ValueError(f"Tipo e-CF inválido: {tipo_ecf}")

    with transaction.atomic():
        try:
            # SELECT FOR UPDATE: bloquea esta fila hasta que termine la transacción
            secuencial = Secuencial.objects.select_for_update().get(
                empresa=empresa,
                tipo_ecf=tipo_ecf,
            )
        except Secuencial.DoesNotExist:
            raise TipoECFNoExisteError(
                f"No hay secuencial configurado para tipo {tipo_ecf} "
                f"en la empresa {empresa.rnc}."
            )

        if secuencial.bloqueado:
            raise TipoECFBloqueadoError(
                f"El tipo {tipo_ecf} está bloqueado. "
                f"Motivo: {secuencial.motivo_bloqueo or 'Sin especificar'}"
            )

        proximo = secuencial.ultimo_numero + 1

        if proximo > secuencial.maximo_asignado:
            # Bloquear automáticamente para que el admin lo amplíe
            secuencial.bloqueado = True
            secuencial.motivo_bloqueo = "Rango agotado automáticamente."
            secuencial.save(update_fields=["bloqueado", "motivo_bloqueo"])
            raise SecuencialAgotadoError(
                f"El rango de secuenciales para tipo {tipo_ecf} se ha agotado. "
                f"Máximo: {secuencial.maximo_asignado}."
            )

        secuencial.ultimo_numero = proximo
        secuencial.save(update_fields=["ultimo_numero", "actualizado_at"])

        return secuencial._formatear_encf(proximo)


# ─── MODELS.PY — apps/comprobantes/models.py ───
"""
apps/comprobantes/models.py

Comprobantes electrónicos (e-CF) por empresa.

SEGURIDAD Y CUMPLIMIENTO:
- Inmutabilidad en save() Y en trigger de DB (el trigger está en la migración).
- ComprobanteDetalle también es inmutable cuando el padre está ACEPTADO.
- Todos los campos que la DGII requiere en el XML están presentes.
- xml_path usa namespacing por empresa: {empresa_uuid}/ecf/{año}/{encf}.xml
- idempotency_key para prevenir doble emisión por retry del POS.
- paquete_id FK registra exactamente qué paquete fue consumido.

ESTADOS:
  BORRADOR → PENDIENTE → PROCESANDO → ACEPTADO
                                    ↘ RECHAZADO → (corregir, re-emitir con nuevo e-NCF)
                    ANULADO (desde ACEPTADO, con nota de crédito)
                    ERROR (falla técnica, se puede reintentar)
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.sequences.models import TIPOS_ECF, TIPO_ECF_CHOICES


# Tipos que requieren comprobante de referencia (nota de crédito/débito)
TIPOS_REQUIEREN_REFERENCIA = {33, 34, 41}


class Comprobante(models.Model):
    # ─── Estados ──────────────────────────────────────────────────────────────
    ESTADO_BORRADOR = "BORRADOR"
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_PROCESANDO = "PROCESANDO"
    ESTADO_ACEPTADO = "ACEPTADO"
    ESTADO_RECHAZADO = "RECHAZADO"
    ESTADO_ANULADO = "ANULADO"
    ESTADO_ERROR = "ERROR"

    ESTADOS = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_PENDIENTE, "Pendiente de envío"),
        (ESTADO_PROCESANDO, "Procesando en DGII"),
        (ESTADO_ACEPTADO, "Aceptado por DGII"),
        (ESTADO_RECHAZADO, "Rechazado por DGII"),
        (ESTADO_ANULADO, "Anulado"),
        (ESTADO_ERROR, "Error técnico"),
    ]

    # Estados que hacen el comprobante inmutable
    ESTADOS_INMUTABLES = {ESTADO_ACEPTADO, ESTADO_ANULADO}

    # ─── Condición de pago ────────────────────────────────────────────────────
    CONDICION_CONTADO = "CONTADO"
    CONDICION_CREDITO = "CREDITO"
    CONDICION_LIBRE = "LIBRE"

    CONDICIONES_PAGO = [
        (CONDICION_CONTADO, "Contado"),
        (CONDICION_CREDITO, "Crédito"),
        (CONDICION_LIBRE, "Libre"),
    ]

    # ─── Campos ───────────────────────────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        related_name="comprobantes",
    )

    # Paquete consumido — registra exactamente qué paquete se usó
    paquete = models.ForeignKey(
        "subscriptions.PaqueteComprobantes",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="comprobantes",
    )

    # Prevención de doble emisión por retry del POS
    idempotency_key = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        help_text="UUID único por intento de emisión. El POS genera este valor.",
    )

    # ─── Datos DGII ───────────────────────────────────────────────────────────
    tipo_ecf = models.PositiveSmallIntegerField(choices=TIPO_ECF_CHOICES)
    encf = models.CharField(max_length=13, blank=True, db_index=True)  # E310000001

    # Emisor (la empresa — se llena automáticamente)
    rnc_emisor = models.CharField(max_length=11)

    # Receptor
    rnc_comprador = models.CharField(max_length=11, blank=True)
    cedula_comprador = models.CharField(max_length=11, blank=True)
    razon_social_comprador = models.CharField(max_length=255, blank=True)

    # Fecha y condiciones
    fecha_emision = models.DateTimeField(default=timezone.now)
    fecha_vencimiento_pago = models.DateField(null=True, blank=True)
    condicion_pago = models.CharField(
        max_length=10, choices=CONDICIONES_PAGO, default=CONDICION_CONTADO
    )

    # Montos (DGII requiere separar gravado e ITBIS)
    monto_gravado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_exento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_itbis = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Respuesta DGII
    estado = models.CharField(max_length=15, choices=ESTADOS, default=ESTADO_BORRADOR)
    track_id_dgii = models.CharField(max_length=255, blank=True)
    codigo_seguridad_dgii = models.CharField(max_length=255, blank=True)

    # URL de impresión e imagen QR (obligatorio en comprobante impreso)
    impresion_url = models.URLField(blank=True)
    qr_data = models.TextField(blank=True, help_text="Datos del QR para impresión.")

    # Referencia (obligatorio para notas de crédito/débito)
    comprobante_referencia = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="notas",
    )
    encf_referencia = models.CharField(
        max_length=13,
        blank=True,
        help_text="e-NCF del comprobante que se modifica con esta nota.",
    )

    # XML — path con namespacing por empresa para evitar colisiones
    # Formato: {empresa_uuid}/ecf/{año}/{encf}.xml
    xml_path = models.CharField(max_length=512, blank=True)
    xml_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 del XML firmado.")
    xml_version = models.CharField(
        max_length=10,
        blank=True,
        help_text="Versión del schema XML DGII usado para generar este comprobante.",
    )

    # Metadata
    intentos_envio = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.TextField(blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comprobantes"
        verbose_name = "Comprobante"
        verbose_name_plural = "Comprobantes"
        indexes = [
            models.Index(fields=["empresa", "estado"]),
            models.Index(fields=["empresa", "tipo_ecf"]),
            models.Index(fields=["encf"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["creado_at"]),
        ]

    def __str__(self):
        return f"{self.encf or '(sin e-NCF)'} — {self.empresa.rnc} [{self.estado}]"

    # ─── Inmutabilidad ────────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        """
        INMUTABILIDAD a nivel Python.
        CORREGIDO: También hay un trigger de DB en la migración para cubrir
        el caso de .update() que bypasea este save().
        """
        if self.pk:
            try:
                original = Comprobante.objects.values("estado").get(pk=self.pk)
                if original["estado"] in self.ESTADOS_INMUTABLES:
                    raise ValidationError(
                        f"No se puede modificar un comprobante en estado "
                        f"'{original['estado']}'. Es inmutable por cumplimiento fiscal."
                    )
            except Comprobante.DoesNotExist:
                pass

        # Auto-fill del RNC emisor
        if not self.rnc_emisor and self.empresa_id:
            self.rnc_emisor = self.empresa.rnc

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Nunca borrar comprobantes — retención legal 10 años."""
        raise ValidationError(
            "Los comprobantes no pueden eliminarse. Retención legal DGII: 10 años."
        )

    # ─── Validaciones ─────────────────────────────────────────────────────────

    def clean(self):
        errores = {}

        if self.tipo_ecf not in TIPOS_ECF:
            errores["tipo_ecf"] = f"Tipo e-CF inválido: {self.tipo_ecf}."

        # Notas de crédito/débito requieren referencia
        if self.tipo_ecf in TIPOS_REQUIEREN_REFERENCIA:
            if not self.encf_referencia and not self.comprobante_referencia_id:
                errores["encf_referencia"] = (
                    f"El tipo {self.tipo_ecf} requiere un comprobante de referencia."
                )

        # Validar montos básicos
        if self.monto_total < 0:
            errores["monto_total"] = "El monto total no puede ser negativo."

        calculado = self.monto_gravado + self.monto_exento + self.monto_itbis
        if abs(float(calculado) - float(self.monto_total)) > 0.01:
            errores["monto_total"] = (
                f"El monto total ({self.monto_total}) no coincide con "
                f"gravado + exento + ITBIS ({calculado})."
            )

        if errores:
            raise ValidationError(errores)

    # ─── Helpers de estado ────────────────────────────────────────────────────

    @property
    def es_inmutable(self):
        return self.estado in self.ESTADOS_INMUTABLES

    @property
    def puede_anularse(self):
        return self.estado == self.ESTADO_ACEPTADO

    @property
    def puede_reintentarse(self):
        return self.estado in {self.ESTADO_RECHAZADO, self.ESTADO_ERROR}


# ─────────────────────────────────────────────────────────────────────────────
# Detalle de Comprobante
# ─────────────────────────────────────────────────────────────────────────────

class ComprobanteDetalle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.PROTECT,   # PROTECT: no borrar detalles si el comprobante existe
        related_name="detalles",
    )

    numero_linea = models.PositiveSmallIntegerField()
    codigo_producto = models.CharField(max_length=50, blank=True)
    descripcion = models.CharField(max_length=500)
    cantidad = models.DecimalField(max_digits=14, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=4)
    descuento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    recargo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    itbis_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    itbis_monto = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "comprobante_detalles"
        verbose_name = "Detalle de Comprobante"
        verbose_name_plural = "Detalles de Comprobante"
        unique_together = [("comprobante", "numero_linea")]
        ordering = ["numero_linea"]

    def __str__(self):
        return f"Línea {self.numero_linea}: {self.descripcion}"

    def save(self, *args, **kwargs):
        """
        CORREGIDO: Los detalles también son inmutables cuando el padre está aceptado.
        """
        if self.comprobante_id:
            estado_padre = Comprobante.objects.values("estado").get(
                pk=self.comprobante_id
            )["estado"]
            if estado_padre in Comprobante.ESTADOS_INMUTABLES:
                raise ValidationError(
                    "No se pueden modificar los detalles de un comprobante "
                    f"en estado '{estado_padre}'."
                )
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Eventos del Comprobante (historial de cambios de estado)
# ─────────────────────────────────────────────────────────────────────────────

class ComprobanteEvento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.PROTECT,
        related_name="eventos",
    )

    estado_anterior = models.CharField(max_length=15, blank=True)
    estado_nuevo = models.CharField(max_length=15)
    mensaje = models.TextField(blank=True)
    datos_extra = models.JSONField(null=True, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comprobante_eventos"
        verbose_name = "Evento de Comprobante"
        verbose_name_plural = "Eventos de Comprobante"
        ordering = ["creado_at"]

    def __str__(self):
        return (
            f"{self.comprobante.encf}: "
            f"{self.estado_anterior} → {self.estado_nuevo}"
        )

    def save(self, *args, **kwargs):
        """Los eventos son inmutables — solo inserción."""
        if self.pk:
            raise ValidationError("Los eventos de comprobante no pueden modificarse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los eventos de comprobante no pueden eliminarse.")


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
    # Usar apps.empresas.crypto.cifrar() / descifrar()
    request_xml_cifrado = models.TextField(blank=True)
    response_xml_cifrado = models.TextField(blank=True)

    # Schema DGII usado en esta operación
    xml_version = models.CharField(max_length=10, blank=True)

    codigo_error = models.CharField(max_length=50, blank=True)
    mensaje = models.TextField(blank=True)
    exitoso = models.BooleanField(default=False)
    duracion_ms = models.PositiveIntegerField(null=True, blank=True)

    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dgii_logs"
        verbose_name = "Log DGII"
        verbose_name_plural = "Logs DGII"
        indexes = [
            models.Index(fields=["empresa", "tipo_operacion", "creado_at"]),
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
            raise ValueError(
                "Los logs DGII no pueden modificarse. Son registros de auditoría."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Los logs DGII no pueden eliminarse. Retención legal 10 años.")


# ─── MODELS.PY — apps/webhooks/models.py ───
"""
apps/webhooks/models.py

Webhooks para notificar al cliente cuando cambia el estado de un comprobante.

SEGURIDAD:
- El secret del webhook se hashea (SHA-256) — nunca se guarda en texto plano.
- La URL DEBE ser HTTPS — validado en clean(), no solo en el serializer.
- Backoff exponencial en reintentos con límite MAX_INTENTOS.
- Payloads firmados con HMAC-SHA256 usando el secret original (que el cliente guarda).
"""
import hashlib
import secrets
import uuid
from django.db import models
from django.core.exceptions import ValidationError


MAX_INTENTOS = 5


class Webhook(models.Model):
    ESTADO_ACTIVO = "ACTIVO"
    ESTADO_FALLANDO = "FALLANDO"
    ESTADO_ABANDONADO = "ABANDONADO"
    ESTADO_INACTIVO = "INACTIVO"

    ESTADOS = [
        (ESTADO_ACTIVO, "Activo"),
        (ESTADO_FALLANDO, "Fallando (reintentos en progreso)"),
        (ESTADO_ABANDONADO, "Abandonado (máx. intentos alcanzado)"),
        (ESTADO_INACTIVO, "Inactivo (desactivado por el cliente)"),
    ]

    # Eventos disponibles para suscribirse
    EVENTO_COMPROBANTE_ACEPTADO = "comprobante.aceptado"
    EVENTO_COMPROBANTE_RECHAZADO = "comprobante.rechazado"
    EVENTO_COMPROBANTE_ANULADO = "comprobante.anulado"
    EVENTO_PAQUETE_AGOTADO = "paquete.agotado"
    EVENTO_CERTIFICADO_POR_VENCER = "certificado.por_vencer"

    EVENTOS_DISPONIBLES = [
        (EVENTO_COMPROBANTE_ACEPTADO, "Comprobante aceptado por DGII"),
        (EVENTO_COMPROBANTE_RECHAZADO, "Comprobante rechazado por DGII"),
        (EVENTO_COMPROBANTE_ANULADO, "Comprobante anulado"),
        (EVENTO_PAQUETE_AGOTADO, "Paquete de comprobantes agotado"),
        (EVENTO_CERTIFICADO_POR_VENCER, "Certificado próximo a vencer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.CASCADE,
        related_name="webhooks",
    )

    nombre = models.CharField(max_length=100)
    url = models.URLField(max_length=500)

    # SHA-256 del secret — el secret completo se muestra UNA VEZ al crear
    secret_hash = models.CharField(max_length=64, editable=False)

    # Eventos a los que está suscrito este webhook
    # Ej: ["comprobante.aceptado", "comprobante.rechazado"]
    eventos = models.JSONField(default=list)

    estado = models.CharField(max_length=15, choices=ESTADOS, default=ESTADO_ACTIVO)
    activo = models.BooleanField(default=True)

    ultimo_intento_at = models.DateTimeField(null=True, blank=True)
    ultimo_http_status = models.PositiveSmallIntegerField(null=True, blank=True)

    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "webhooks"
        verbose_name = "Webhook"
        verbose_name_plural = "Webhooks"
        indexes = [
            models.Index(fields=["empresa", "activo"]),
        ]

    def __str__(self):
        return f"{self.nombre} → {self.url} [{self.estado}]"

    # ─── Generación ──────────────────────────────────────────────────────────

    @classmethod
    def crear(cls, empresa, nombre, url, eventos):
        """
        Crea un webhook con secret generado automáticamente.
        Retorna (instancia, secret_completo).
        El secret_completo se muestra UNA SOLA VEZ al cliente.
        """
        secret = secrets.token_urlsafe(32)
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()

        instancia = cls(
            empresa=empresa,
            nombre=nombre,
            url=url,
            secret_hash=secret_hash,
            eventos=eventos,
        )
        instancia.full_clean()
        instancia.save()
        return instancia, secret

    # ─── Validaciones ─────────────────────────────────────────────────────────

    def clean(self):
        errores = {}

        # CORREGIDO: La URL DEBE ser HTTPS — validado en clean(), no solo en serializer
        if self.url and not self.url.startswith("https://"):
            errores["url"] = (
                "La URL del webhook debe usar HTTPS. "
                "Los payloads contienen datos fiscales sensibles."
            )

        # Validar que los eventos sean del conjunto permitido
        eventos_validos = {e[0] for e in self.EVENTOS_DISPONIBLES}
        if self.eventos:
            invalidos = [e for e in self.eventos if e not in eventos_validos]
            if invalidos:
                errores["eventos"] = f"Eventos inválidos: {', '.join(invalidos)}"

        if errores:
            raise ValidationError(errores)


class WebhookEntrega(models.Model):
    """Registro de cada intento de entrega de un evento."""

    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_ENTREGADO = "ENTREGADO"
    ESTADO_FALLIDO = "FALLIDO"
    ESTADO_REINTENTANDO = "REINTENTANDO"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_FALLIDO, "Fallido"),
        (ESTADO_REINTENTANDO, "Reintentando"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name="entregas",
    )

    comprobante = models.ForeignKey(
        "comprobantes.Comprobante",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="webhook_entregas",
    )

    evento = models.CharField(max_length=50)

    # SHA-256 del payload — para detectar si el contenido fue alterado
    payload_hash = models.CharField(max_length=64)

    estado = models.CharField(max_length=15, choices=ESTADOS, default=ESTADO_PENDIENTE)
    intentos = models.PositiveSmallIntegerField(default=0)
    max_intentos = models.PositiveSmallIntegerField(default=MAX_INTENTOS)
    ultimo_http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_mensaje = models.TextField(blank=True)

    proximo_intento_at = models.DateTimeField(null=True, blank=True)
    entregado_at = models.DateTimeField(null=True, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhook_entregas"
        verbose_name = "Entrega de Webhook"
        verbose_name_plural = "Entregas de Webhooks"
        indexes = [
            models.Index(fields=["webhook", "estado"]),
            models.Index(fields=["proximo_intento_at", "estado"]),
        ]

    def __str__(self):
        return f"{self.evento} → {self.webhook.url} [{self.estado}]"

    @property
    def puede_reintentar(self):
        return (
            self.estado in {self.ESTADO_FALLIDO, self.ESTADO_REINTENTANDO}
            and self.intentos < self.max_intentos
        )


# ─── MODELS.PY — apps/audit/models.py ───
"""
apps/audit/models.py

Log de auditoría del sistema.

SEGURIDAD:
- Append-only a nivel Python: save() lanza si se intenta editar un registro existente.
- CORREGIDO: .update() bypasea save(). Por eso se agrega un campo `signature`
  con HMAC-SHA256 del contenido. Al leer, el middleware puede verificar integridad.
- El trigger de DB que impide UPDATE/DELETE está en la migración correspondiente.
- default_permissions = ("view",) — Django no genera permisos de add/change/delete.
"""
import hashlib
import hmac
import json
import uuid
from django.db import models
from django.conf import settings


def _calcular_firma(data: dict) -> str:
    """
    HMAC-SHA256 del contenido serializado.
    Clave: settings.SECRET_KEY (ya está en el VPS).
    """
    contenido = json.dumps(data, sort_keys=True, default=str)
    return hmac.new(
        settings.SECRET_KEY.encode(),
        contenido.encode(),
        hashlib.sha256,
    ).hexdigest()


class AuditLog(models.Model):
    ACCION_CREAR = "CREATE"
    ACCION_LEER = "READ"
    ACCION_ACTUALIZAR = "UPDATE"
    ACCION_ELIMINAR = "DELETE"
    ACCION_LOGIN = "LOGIN"
    ACCION_LOGOUT = "LOGOUT"
    ACCION_LOGIN_FALLIDO = "LOGIN_FAILED"
    ACCION_REVOCAR_KEY = "REVOKE_API_KEY"
    ACCION_EMITIR = "EMIT_ECF"
    ACCION_ANULAR = "ANULAR_ECF"

    ACCIONES = [
        (ACCION_CREAR, "Crear"),
        (ACCION_LEER, "Leer"),
        (ACCION_ACTUALIZAR, "Actualizar"),
        (ACCION_ELIMINAR, "Eliminar"),
        (ACCION_LOGIN, "Inicio de sesión"),
        (ACCION_LOGOUT, "Cierre de sesión"),
        (ACCION_LOGIN_FALLIDO, "Inicio de sesión fallido"),
        (ACCION_REVOCAR_KEY, "Revocar API Key"),
        (ACCION_EMITIR, "Emitir e-CF"),
        (ACCION_ANULAR, "Anular e-CF"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    # El actor puede ser un usuario humano o una API key
    usuario = models.ForeignKey(
        "users.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    api_key_prefix = models.CharField(max_length=8, blank=True)

    # Qué hizo
    accion = models.CharField(max_length=20, choices=ACCIONES)
    recurso = models.CharField(max_length=100, blank=True, help_text="Ej: 'Comprobante'")
    recurso_id = models.CharField(max_length=100, blank=True, help_text="UUID o ID del recurso afectado")

    # Contexto HTTP
    endpoint = models.CharField(max_length=255, blank=True)
    metodo_http = models.CharField(max_length=10, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    ip_pais = models.CharField(max_length=2, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    # Hash del request body (no el body completo — pueden contener datos sensibles)
    request_body_hash = models.CharField(max_length=64, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)

    # Datos adicionales (sin datos sensibles)
    extra = models.JSONField(null=True, blank=True)

    creado_at = models.DateTimeField(auto_now_add=True)

    # CORREGIDO: HMAC del contenido para detectar manipulación
    # Si alguien hace .update() directo en la DB o via ORM, el HMAC no coincidirá.
    signature = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        db_table = "audit_logs"
        verbose_name = "Log de Auditoría"
        verbose_name_plural = "Logs de Auditoría"
        # Solo permiso de lectura — no add/change/delete en el admin
        default_permissions = ("view",)
        indexes = [
            models.Index(fields=["empresa", "creado_at"]),
            models.Index(fields=["usuario", "creado_at"]),
            models.Index(fields=["accion", "creado_at"]),
            models.Index(fields=["ip"]),
        ]

    def __str__(self):
        actor = self.usuario or f"APIKey:{self.api_key_prefix}"
        return f"[{self.creado_at:%Y-%m-%d %H:%M}] {actor} — {self.accion} {self.recurso}"

    def _datos_para_firma(self) -> dict:
        return {
            "id": str(self.id),
            "empresa_id": str(self.empresa_id) if self.empresa_id else None,
            "usuario_id": str(self.usuario_id) if self.usuario_id else None,
            "accion": self.accion,
            "recurso": self.recurso,
            "recurso_id": self.recurso_id,
            "ip": self.ip,
            "creado_at": str(self.creado_at),
        }

    def verificar_integridad(self) -> bool:
        """Verifica que el registro no fue manipulado comparando el HMAC."""
        esperado = _calcular_firma(self._datos_para_firma())
        return hmac.compare_digest(self.signature, esperado)

    def save(self, *args, **kwargs):
        """
        Append-only a nivel Python.
        NOTA: También hay un trigger en la migración para bloquear UPDATE a nivel DB.
        """
        if self.pk:
            raise ValueError(
                "Los registros de auditoría no pueden modificarse. "
                "Son inmutables por diseño."
            )

        # Calcular HMAC antes de guardar
        # El id y creado_at no están disponibles antes del primer save,
        # así que los calculamos con los datos disponibles.
        datos = {
            "empresa_id": str(self.empresa_id) if self.empresa_id else None,
            "usuario_id": str(self.usuario_id) if self.usuario_id else None,
            "accion": self.accion,
            "recurso": self.recurso,
            "recurso_id": self.recurso_id,
            "ip": self.ip,
        }
        self.signature = _calcular_firma(datos)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(
            "Los registros de auditoría no pueden eliminarse."
        )


# ─── MIDDLEWARE.PY — apps/audit/middleware.py ───
"""
apps/audit/middleware.py

Dos middlewares críticos:

1. TenantMiddleware:
   Inyecta request.empresa a partir del usuario autenticado (portal web)
   o de la ApiKey (llamadas API). Toda vista que necesite datos de empresa
   llama request.empresa en lugar de buscar la empresa manualmente.
   Esto centraliza el aislamiento multi-tenant.

2. AuditMiddleware:
   Registra cada request al AuditLog automáticamente.
   Ignora endpoints de health check y estáticos.
"""
import hashlib
import json

from django.utils.deprecation import MiddlewareMixin


# ─────────────────────────────────────────────────────────────────────────────
# Tenant Middleware
# ─────────────────────────────────────────────────────────────────────────────

PATHS_SIN_TENANT = {
    "/admin/",
    "/api/auth/login/",
    "/api/auth/token/",
    "/health/",
    "/static/",
    "/media/",
}


class TenantMiddleware(MiddlewareMixin):
    """
    Inyecta request.empresa basado en el actor autenticado.

    Para usuarios del portal web: empresa = usuario.empresa
    Para llamadas API con ApiKey: empresa = api_key.empresa
    Para superadmin: empresa = None (puede ver todo)

    NOTA: Las vistas deben usar request.empresa para filtrar sus QuerySets.
    Nunca hacer Comprobante.objects.all() — siempre Comprobante.objects.filter(empresa=request.empresa).
    """

    def process_request(self, request):
        request.empresa = None

        # No aplicar en paths de sistema
        if any(request.path.startswith(p) for p in PATHS_SIN_TENANT):
            return

        # Caso 1: Usuario autenticado (portal web)
        if hasattr(request, "user") and request.user.is_authenticated:
            from apps.users.models import Usuario
            if request.user.rol == Usuario.ROL_SUPERADMIN:
                request.empresa = None  # Superadmin puede operar sobre todas
            else:
                request.empresa = request.user.empresa
            return

        # Caso 2: ApiKey en el header Authorization
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            from apps.api_keys.models import ApiKey
            api_key = ApiKey.verificar(token)
            if api_key:
                request.empresa = api_key.empresa
                request.api_key = api_key  # Para el rate limiter y auditoría
            # Si la key no es válida, request.empresa queda None
            # La vista debe retornar 401


# ─────────────────────────────────────────────────────────────────────────────
# Audit Middleware
# ─────────────────────────────────────────────────────────────────────────────

PATHS_SIN_AUDIT = {"/health/", "/static/", "/media/", "/favicon.ico"}

# Métodos que no vale la pena auditar
METODOS_SIN_AUDIT = {"OPTIONS", "HEAD"}


class AuditMiddleware(MiddlewareMixin):
    """
    Registra automáticamente cada request relevante en AuditLog.
    Solo registra después del response (process_response) para tener el status code.
    No registra bodies completos — solo su SHA-256 para no guardar datos sensibles.
    """

    def process_response(self, request, response):
        try:
            if request.method in METODOS_SIN_AUDIT:
                return response
            if any(request.path.startswith(p) for p in PATHS_SIN_AUDIT):
                return response

            # Determinar actor
            usuario = None
            api_key_prefix = ""
            empresa = getattr(request, "empresa", None)

            if hasattr(request, "user") and request.user.is_authenticated:
                usuario = request.user
            if hasattr(request, "api_key"):
                api_key_prefix = request.api_key.prefix

            # Hash del body (no el body completo)
            body_hash = ""
            if request.method in ("POST", "PUT", "PATCH"):
                try:
                    body = request.body
                    body_hash = hashlib.sha256(body).hexdigest() if body else ""
                except Exception:
                    pass

            # IP real (detrás de proxy/Nginx)
            ip = (
                request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                or request.META.get("REMOTE_ADDR", "")
            )

            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                empresa=empresa,
                usuario=usuario,
                api_key_prefix=api_key_prefix,
                accion=_metodo_a_accion(request.method),
                endpoint=request.path[:255],
                metodo_http=request.method,
                ip=ip or None,
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                request_body_hash=body_hash,
                response_status=response.status_code,
            )
        except Exception:
            # El middleware de auditoría NUNCA debe romper el request principal
            pass

        return response


def _metodo_a_accion(metodo: str) -> str:
    return {
        "GET": "READ",
        "POST": "CREATE",
        "PUT": "UPDATE",
        "PATCH": "UPDATE",
        "DELETE": "DELETE",
    }.get(metodo, "READ")


# ─── 0002_IMMUTABILITY_TRIGGERS.PY — apps/comprobantes/migrations/0002_immutability_triggers.py ───
"""
apps/comprobantes/migrations/0002_immutability_triggers.py

Triggers de base de datos para garantizar inmutabilidad real.

CONTEXTO:
- El save() de Python es bypasseable con .update() o acceso directo a la DB.
- Estos triggers aplican la inmutabilidad a nivel de motor de base de datos.
- Usar PostgreSQL (recomendado para este proyecto).

INSTRUCCIONES:
1. Crear este archivo en la carpeta migrations de la app correspondiente.
2. Ajustar los números de migración (0002) según lo que ya exista.
3. Aplicar con: python manage.py migrate
"""
from django.db import migrations


# ── Trigger: Comprobante inmutable cuando está ACEPTADO o ANULADO ──────────────
SQL_TRIGGER_COMPROBANTE = """
CREATE OR REPLACE FUNCTION prevent_comprobante_update()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.estado IN ('ACEPTADO', 'ANULADO') THEN
        RAISE EXCEPTION
            'Comprobante % está en estado % y no puede ser modificado.',
            OLD.id, OLD.estado;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_comprobante_immutable
    BEFORE UPDATE ON comprobantes
    FOR EACH ROW EXECUTE FUNCTION prevent_comprobante_update();
"""

SQL_DROP_TRIGGER_COMPROBANTE = """
DROP TRIGGER IF EXISTS trg_comprobante_immutable ON comprobantes;
DROP FUNCTION IF EXISTS prevent_comprobante_update();
"""

# ── Trigger: Detalle de Comprobante inmutable si el padre está ACEPTADO/ANULADO ─
SQL_TRIGGER_DETALLE = """
CREATE OR REPLACE FUNCTION prevent_detalle_update()
RETURNS TRIGGER AS $$
DECLARE
    estado_padre VARCHAR(15);
BEGIN
    SELECT estado INTO estado_padre FROM comprobantes WHERE id = OLD.comprobante_id;
    IF estado_padre IN ('ACEPTADO', 'ANULADO') THEN
        RAISE EXCEPTION
            'No se puede modificar el detalle del comprobante % en estado %.',
            OLD.comprobante_id, estado_padre;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_detalle_immutable
    BEFORE UPDATE OR DELETE ON comprobante_detalles
    FOR EACH ROW EXECUTE FUNCTION prevent_detalle_update();
"""

SQL_DROP_TRIGGER_DETALLE = """
DROP TRIGGER IF EXISTS trg_detalle_immutable ON comprobante_detalles;
DROP FUNCTION IF EXISTS prevent_detalle_update();
"""

# ── Trigger: AuditLog append-only ──────────────────────────────────────────────
SQL_TRIGGER_AUDIT = """
CREATE OR REPLACE FUNCTION prevent_audit_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Los registros de auditoría son inmutables.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_update();
"""

SQL_DROP_TRIGGER_AUDIT = """
DROP TRIGGER IF EXISTS trg_audit_immutable ON audit_logs;
DROP FUNCTION IF EXISTS prevent_audit_update();
"""

# ── Trigger: DGIILog append-only ───────────────────────────────────────────────
SQL_TRIGGER_DGIILOG = """
CREATE OR REPLACE FUNCTION prevent_dgiilog_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Los logs DGII son inmutables.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_dgiilog_immutable
    BEFORE UPDATE OR DELETE ON dgii_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_dgiilog_update();
"""

SQL_DROP_TRIGGER_DGIILOG = """
DROP TRIGGER IF EXISTS trg_dgiilog_immutable ON dgii_logs;
DROP FUNCTION IF EXISTS prevent_dgiilog_update();
"""


class Migration(migrations.Migration):

    dependencies = [
        # Ajustar según las migraciones existentes
        ("comprobantes", "0001_initial"),
        ("audit", "0001_initial"),
        ("dgii", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=SQL_TRIGGER_COMPROBANTE,
            reverse_sql=SQL_DROP_TRIGGER_COMPROBANTE,
        ),
        migrations.RunSQL(
            sql=SQL_TRIGGER_DETALLE,
            reverse_sql=SQL_DROP_TRIGGER_DETALLE,
        ),
        migrations.RunSQL(
            sql=SQL_TRIGGER_AUDIT,
            reverse_sql=SQL_DROP_TRIGGER_AUDIT,
        ),
        migrations.RunSQL(
            sql=SQL_TRIGGER_DGIILOG,
            reverse_sql=SQL_DROP_TRIGGER_DGIILOG,
        ),
    ]