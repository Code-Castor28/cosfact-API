# Create your models here.
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

