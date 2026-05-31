from rest_framework import serializers
from core.serializers import CleanModelSerializer
from .models import Plan, Suscripcion, PaqueteComprobantes


class PlanSerializer(CleanModelSerializer):
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
            "dias_gracia",
            "tipos_ecf_permitidos",
            "activo",
            "orden",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = ["id", "creado_at", "actualizado_at"]


class SuscripcionSerializer(CleanModelSerializer):
    dias_gracia = serializers.IntegerField(source="plan.dias_gracia", read_only=True)
    
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
            "dias_gracia",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = ["id", "dias_gracia", "creado_at", "actualizado_at"]


class PaqueteComprobantesSerializer(CleanModelSerializer):
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
        # Agregados comprobantes_usados y estado por seguridad (solo el sistema debe cambiarlos)
        read_only_fields = ["id", "fecha_compra", "creado_at", "comprobantes_usados", "estado"]

