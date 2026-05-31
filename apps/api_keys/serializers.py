from rest_framework import serializers
from core.serializers import CleanModelSerializer
from django.core.exceptions import ValidationError as DjangoValidationError  # type: ignore[import-untyped]
from empresas.models import Empresa
from .models import ApiKey


class EmpresaMiniSerializer(CleanModelSerializer):
    class Meta:
        model = Empresa
        fields = ["id", "razon_social", "rnc"]


class ApiKeyReadSerializer(CleanModelSerializer):
    empresa_detalle = EmpresaMiniSerializer(source="empresa", read_only=True)

    class Meta:
        model = ApiKey
        fields = [
            "id",
            "empresa",
            "empresa_detalle",
            "nombre",
            "prefix",
            "scopes",
            "allowed_ips",
            "rate_limit_cantidad",
            "rate_limit_ventana",
            "activa",
            "expira_at",
            "revocado_at",
            "revocado_por",
            "revocado_motivo",
            "ultimo_uso_at",
            "ultimo_uso_ip",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = [
            "id",
            "prefix",
            "revocado_at",
            "revocado_por",
            "revocado_motivo",
            "ultimo_uso_at",
            "ultimo_uso_ip",
            "creado_at",
            "actualizado_at",
        ]


class ApiKeyWriteSerializer(CleanModelSerializer):
    class Meta:
        model = ApiKey
        fields = [
            "empresa",
            "nombre",
            "scopes",
            "allowed_ips",
            "rate_limit_cantidad",
            "rate_limit_ventana",
            "expira_at",
            "activa",
        ]

    def validate_scopes(self, value):
        if value is None:
            return value
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Los scopes deben ser una lista.")
        invalidos = [s for s in value if s not in ApiKey.SCOPES_VALIDOS]
        if invalidos:
            raise serializers.ValidationError(
                f"Scopes inválidos: {', '.join(invalidos)}."
            )
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        creado_por = getattr(request, "user", None)

        try:
            instancia, token = ApiKey.crear(
                empresa=validated_data["empresa"],
                nombre=validated_data["nombre"],
                creado_por=creado_por,
                scopes=validated_data.get("scopes") or [],
                allowed_ips=validated_data.get("allowed_ips") or [],
                rate_limit_cantidad=validated_data.get(
                    "rate_limit_cantidad", 100),
                rate_limit_ventana=validated_data.get(
                    "rate_limit_ventana", ApiKey.VENTANA_HORA),
                expira_at=validated_data.get("expira_at"),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        # Guardar el token en memoria para retornarlo solo en la respuesta de creacion
        instancia._token_completo = token
        return instancia
