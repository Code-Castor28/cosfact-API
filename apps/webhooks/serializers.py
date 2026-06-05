from rest_framework import serializers
from .models import Webhook, WebhookEntrega


class WebhookSerializer(serializers.ModelSerializer):
    secret = serializers.CharField(read_only=True)

    class Meta:
        model = Webhook
        fields = [
            "id", "nombre", "url", "eventos", "estado", "activo",
            "ultimo_intento_at", "ultimo_http_status", "secret",
            "creado_at", "actualizado_at",
        ]
        read_only_fields = [
            "id", "estado", "ultimo_intento_at",
            "ultimo_http_status", "secret", "creado_at", "actualizado_at",
        ]


class WebhookEntregaSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEntrega
        fields = [
            "id", "evento", "estado", "intentos", "max_intentos",
            "ultimo_http_status", "error_mensaje", "proximo_intento_at",
            "entregado_at", "creado_at",
        ]
        read_only_fields = fields
