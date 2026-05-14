from rest_framework import serializers
from .models import Plan, Suscripcion, PaqueteComprobantes


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "nombre",
            "descripcion",
            "limite_comprobantes",
            "precio_mensual",
            "precio_anual",
            "ciclo_disponible",
            "tipos_ecf_permitidos",
            "activo",
            "orden",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = ["id", "creado_at", "actualizado_at"]


class SuscripcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Suscripcion
        fields = [
            "id",
            "empresa",
            "plan",
            "ciclo",
            "estado",
            "fecha_inicio",
            "fecha_renovacion",
            "precio_pagado",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = ["id", "creado_at", "actualizado_at"]


class PaqueteComprobantesSerializer(serializers.ModelSerializer):
    comprobantes_restantes = serializers.IntegerField(read_only=True)

    class Meta:
        model = PaqueteComprobantes
        fields = [
            "id",
            "empresa",
            "suscripcion",
            "plan",
            "total_comprobantes",
            "comprobantes_usados",
            "comprobantes_restantes",
            "estado",
            "origen",
            "fecha_compra",
            "fecha_vencimiento",
            "creado_at",
        ]
        read_only_fields = ["id", "fecha_compra", "creado_at"]
