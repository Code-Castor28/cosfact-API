from rest_framework import serializers
from .models import Pago, HistorialPago


class PagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = [
            "id",
            "empresa",
            "suscripcion",
            "plan",
            "monto",
            "moneda",
            "metodo_pago",
            "referencia",
            "fecha_pago",
            "fecha_corte",
            "observaciones",
            "estado",
            "confirmado_por",
            "fecha_confirmacion",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = [
            "id",
            "estado",
            "confirmado_por",
            "fecha_confirmacion",
            "creado_at",
            "actualizado_at",
        ]


class PagoDetailSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    empresa_rnc = serializers.CharField(source="empresa.rnc", read_only=True)
    plan_nombre = serializers.CharField(source="plan.nombre", read_only=True)
    confirmado_por_username = serializers.CharField(
        source="confirmado_por.username", read_only=True
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
            "fecha_corte",
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
            "estado",
            "confirmado_por",
            "confirmado_por_username",
            "fecha_confirmacion",
            "creado_at",
            "actualizado_at",
        ]


class HistorialPagoSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
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