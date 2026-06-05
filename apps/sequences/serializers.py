import re

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
            "fecha_bloqueo",
            "usuario_bloqueo",
            "proximo_encf",
            "porcentaje_uso",
            "casi_agotado",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = [
            "id", "creado_at", "actualizado_at", "proximo_encf",
            "fecha_bloqueo", "usuario_bloqueo",
        ]

    def get_proximo_encf(self, obj):
        return obj.proximo_encf()


class SecuenciaItemSerializer(serializers.Serializer):
    desde = serializers.CharField(max_length=13)
    hasta = serializers.CharField(max_length=13)

    def validate(self, attrs):
        if not re.match(r"^E\d{12}$", attrs["desde"]):
            raise serializers.ValidationError(
                "Formato inválido en 'desde'. Debe ser E + 12 dígitos."
            )
        if not re.match(r"^E\d{12}$", attrs["hasta"]):
            raise serializers.ValidationError(
                "Formato inválido en 'hasta'. Debe ser E + 12 dígitos."
            )
        if attrs["desde"][1:3] != attrs["hasta"][1:3]:
            raise serializers.ValidationError(
                "'desde' y 'hasta' deben ser del mismo tipo e-CF."
            )
        desde_num = int(attrs["desde"][3:])
        hasta_num = int(attrs["hasta"][3:])
        if desde_num > hasta_num:
            raise serializers.ValidationError(
                "'desde' no puede ser mayor que 'hasta'."
            )
        attrs["volumen"] = hasta_num - desde_num + 1
        attrs["tipo_ecf"] = int(attrs["desde"][1:3])
        return attrs


class OnboardingSerializer(serializers.Serializer):
    actualizar_certificado = serializers.BooleanField(default=False)
    archivo_p12 = serializers.FileField(required=False, allow_null=True)
    pin_texto_plano = serializers.CharField(
        required=False, allow_null=True, write_only=True
    )
    secuencias = SecuenciaItemSerializer(many=True, min_length=1)

    def validate(self, attrs):
        if attrs.get("actualizar_certificado"):
            if not attrs.get("archivo_p12") or not attrs.get("pin_texto_plano"):
                raise serializers.ValidationError(
                    "archivo_p12 y pin_texto_plano son obligatorios "
                    "para actualizar el certificado."
                )
        return attrs
