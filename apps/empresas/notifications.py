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