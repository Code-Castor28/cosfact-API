from rest_framework import serializers
from core.serializers import CleanModelSerializer
from .models import Pago, HistorialPago


class PagoSerializer(CleanModelSerializer):
    empresa_nombre = serializers.CharField(
        source="empresa.razon_social", read_only=True)
    plan_nombre = serializers.CharField(source="plan.nombre", read_only=True)

    class Meta:
        model = Pago
        fields = [
            "id",
            "empresa",
            "empresa_nombre",
            "suscripcion",
            "plan",
            "plan_nombre",
            "monto",
            "moneda",
            "metodo_pago",
            "referencia",
            "fecha_pago",
            "observaciones",
            "estado",
            "confirmado_por",
            "fecha_confirmacion",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = [
            "id",
            "empresa",
            "empresa_nombre",
            "suscripcion",
            "plan",
            "plan_nombre",
            "monto",
            "moneda",
            "fecha_pago",
            "estado",
            "confirmado_por",
            "fecha_confirmacion",
            "creado_at",
            "actualizado_at",
        ]


class PagoCreateSerializer(CleanModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.razon_social", read_only=True)
    plan_nombre = serializers.CharField(source="plan.nombre", read_only=True)

    class Meta:
        model = Pago
        fields = [
            "id",
            "empresa",
            "empresa_nombre",
            "suscripcion",
            "plan",
            "plan_nombre",
            "monto",
            "moneda",
            "tipo_pago",
            "metodo_pago",
            "referencia",
            "observaciones",
            "estado",
            "creado_at",
        ]
        read_only_fields = ["id", "estado", "creado_at"]
        extra_kwargs = {
            "monto": {"required": False},
            "empresa": {"required": True},
            "suscripcion": {"required": True},
            "plan": {"required": True},
        }


class PagoUpdateSerializer(CleanModelSerializer):
    """
    Serializer SOLO para actualizar método de pago y confirmar.
    Solo permite editar:
    - metodo_pago
    - referencia
    - observaciones

    Todos los otros campos son read-only.
    """

    class Meta:
        model = Pago
        fields = [
            "id",
            "metodo_pago",
            "referencia",
            "observaciones",
            "estado",
        ]
        read_only_fields = [
            "id",
            "estado",
        ]

    def validate(self, attrs):
        """
        Si metodo_pago != EFECTIVO, referencia es requerida.
        """
        # Obtener metodo_pago: del attrs o del objeto existente
        instance = self.instance
        metodo = attrs.get(
            'metodo_pago', instance.metodo_pago if instance else None)
        referencia = attrs.get(
            'referencia', instance.referencia if instance else '').strip()

        if metodo and metodo != Pago.METODO_EFECTIVO:
            if not referencia:
                raise serializers.ValidationError({
                    "referencia": f"Requerida para pagos por {metodo}"
                })

        return attrs


class PagoDetailSerializer(CleanModelSerializer):
    """
    Serializer detallado para ver un pago específico.
    Incluye nombres relacionados (empresa, plan, usuario) como read-only.
    """
    empresa_nombre = serializers.CharField(
        source="empresa.razon_social", read_only=True)
    empresa_rnc = serializers.CharField(source="empresa.rnc", read_only=True)
    plan_nombre = serializers.CharField(source="plan.nombre", read_only=True)
    confirmado_por_username = serializers.CharField(
        source="confirmado_por.email", read_only=True
    )

    class Meta:
        model = Pago
        fields = [
            "id",
            "empresa",
            "empresa_nombre",
            "empresa_rnc",
            "suscripcion",
            "plan",
            "plan_nombre",
            "monto",
            "moneda",
            "metodo_pago",
            "referencia",
            "fecha_pago",
            "observaciones",
            "estado",
            "confirmado_por",
            "confirmado_por_username",
            "fecha_confirmacion",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = [
            "id",
            "empresa",
            "empresa_nombre",
            "empresa_rnc",
            "suscripcion",
            "plan",
            "plan_nombre",
            "monto",
            "moneda",
            "fecha_pago",
            "estado",
            "confirmado_por",
            "confirmado_por_username",
            "fecha_confirmacion",
            "creado_at",
            "actualizado_at",
        ]


class HistorialPagoSerializer(CleanModelSerializer):
    """
    Serializer para el historial de pagos confirmados.
    Todos los campos son read-only (es historial).
    """
    empresa_nombre = serializers.CharField(
        source="empresa.razon_social", read_only=True)
    empresa_rnc = serializers.CharField(source="empresa.rnc", read_only=True)
    plan_nombre = serializers.CharField(source="plan.nombre", read_only=True)

    class Meta:
        model = HistorialPago
        fields = [
            "id",
            "empresa",
            "empresa_nombre",
            "empresa_rnc",
            "suscripcion",
            "plan",
            "plan_nombre",
            "pago",
            "paquete",
            "periodo_mes",
            "periodo_ano",
            "monto_pagado",
            "comprobantes_asignados",
            "creado_at",
        ]
        read_only_fields = ["id", "creado_at"]
