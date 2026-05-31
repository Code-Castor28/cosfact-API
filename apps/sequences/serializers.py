from rest_framework import serializers
from core.serializers import CleanModelSerializer
from .models import Secuencial


class SecuencialSerializer(CleanModelSerializer):
    proximo_encf = serializers.SerializerMethodField()
    porcentaje_uso = serializers.FloatField(read_only=True)
    casi_agotado = serializers.BooleanField(read_only=True)

    class Meta:
        model = Secuencial
        fields = [
            "id",
            "empresa",
            "tipo_ecf",
            "ultimo_numero",
            "minimo_asignado",
            "maximo_asignado",
            "bloqueado",
            "motivo_bloqueo",
            "proximo_encf",
            "porcentaje_uso",
            "casi_agotado",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = ["id", "creado_at",
                            "actualizado_at", "proximo_encf"]

    def get_proximo_encf(self, obj):
        return obj.proximo_encf()
