from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
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
            "dias_gracia",
            "tipos_ecf_permitidos",
            "activo",
            "orden",
            "creado_at",
            "actualizado_at",
        ]
        read_only_fields = ["id", "creado_at", "actualizado_at"]

    def validate(self, attrs):
        # Instanciar el modelo en memoria para validar
        instance = Plan(**attrs)
        if self.instance:
            # Si es una actualización, aplicamos los cambios a la instancia existente
            for attr, value in attrs.items():
                setattr(instance, attr, value)
        
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Convertir el error de Django al formato de DRF para que el frontend lo consuma
            if hasattr(e, 'message_dict'):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError(e.messages)
            
        return attrs


class SuscripcionSerializer(serializers.ModelSerializer):
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
        # Agregados comprobantes_usados y estado por seguridad (solo el sistema debe cambiarlos)
        read_only_fields = ["id", "fecha_compra", "creado_at", "comprobantes_usados", "estado"]

    def validate(self, attrs):
        # Instanciar el modelo en memoria para validar
        instance = PaqueteComprobantes(**attrs)
        if self.instance:
            for attr, value in attrs.items():
                setattr(instance, attr, value)
        
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Convertir el error de Django al formato de DRF
            if hasattr(e, 'message_dict'):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError(e.messages)
            
        return attrs
