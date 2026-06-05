from rest_framework import serializers
from .models import Cliente


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = [
            'id', 'rnc_cedula', 'razon_social', 'direccion',
            'email', 'telefono', 'creado_at', 'actualizado_at',
        ]
        read_only_fields = ['id', 'creado_at', 'actualizado_at']

    def validate_rnc_cedula(self, value):
        if not value.isdigit():
            raise serializers.ValidationError(
                "RNC/Cédula debe contener solo dígitos numéricos."
            )
        if len(value) not in (9, 11):
            raise serializers.ValidationError(
                "RNC/Cédula debe tener 9 dígitos (Jurídico) o 11 dígitos (Físico)."
            )
        return value
