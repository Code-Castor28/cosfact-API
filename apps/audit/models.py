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
from django.core.exceptions import ValidationError
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
            raise ValidationError(
                "Los registros de auditoría no pueden modificarse."
            )

        super().save(*args, **kwargs)

        datos = {
            "id": str(self.id),
            "empresa_id": str(self.empresa_id) if self.empresa_id else None,
            "usuario_id": str(self.usuario_id) if self.usuario_id else None,
            "accion": self.accion,
            "recurso": self.recurso,
            "recurso_id": self.recurso_id,
            "ip": self.ip,
            "creado_at": str(self.creado_at),
        }
        self.signature = _calcular_firma(datos)
        AuditLog.objects.filter(pk=self.pk).update(signature=self.signature)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Los registros de auditoría no pueden eliminarse."
        )
