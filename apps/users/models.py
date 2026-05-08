
# Create your models here.
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
