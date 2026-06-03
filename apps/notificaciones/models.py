from django.db import models


class LogNotificacion(models.Model):
    CANAL_CORREO = "CORREO"
    CANALES = [(CANAL_CORREO, "Correo electrónico")]

    TIPO_RECIBO_PAGO = "RECIBO_PAGO"
    TIPO_BALANCE_BAJO = "BALANCE_BAJO"
    TIPO_CERTIFICADO_VENCER = "CERTIFICADO_VENCER"
    TIPO_SUSCRIPCION_VENCER = "SUSCRIPCION_VENCER"

    TIPOS = [
        (TIPO_RECIBO_PAGO, "Recibo de pago"),
        (TIPO_BALANCE_BAJO, "Balance bajo"),
        (TIPO_CERTIFICADO_VENCER, "Certificado por vencer"),
        (TIPO_SUSCRIPCION_VENCER, "Suscripción por vencer"),
    ]

    ESTADO_ENVIADO = "ENVIADO"
    ESTADO_FALLIDO = "FALLIDO"
    ESTADOS = [
        (ESTADO_ENVIADO, "Enviado"),
        (ESTADO_FALLIDO, "Fallido"),
    ]

    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.CASCADE,
        related_name="logs_notificaciones",
    )
    destinatario = models.EmailField()
    canal = models.CharField(max_length=10, choices=CANALES, default=CANAL_CORREO)
    tipo = models.CharField(max_length=30, choices=TIPOS)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ESTADO_ENVIADO)
    asunto = models.CharField(max_length=255)
    error_mensaje = models.TextField(blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notificaciones_log"
        verbose_name = "Log de notificación"
        verbose_name_plural = "Logs de notificaciones"
        ordering = ["-creado_at"]

    def __str__(self):
        return f"{self.tipo} → {self.destinatario} [{self.estado}]"
