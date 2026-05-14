# apps/empresas/serializers.py
"""
Serializers para la app empresas.

Hay 3 niveles de acceso:
  - Superadmin → ve y modifica todo (EmpresaDetailSerializer / EmpresaWriteSerializer)
  - Admin Empresa → solo lectura reducida de su empresa (EmpresaAdminSerializer)
  - Resúmenes de Suscripción y Paquetes para los endpoints /suscripcion/ y /comprobantes/
"""
from rest_framework import serializers
from .models import Empresa, TokenDGII
from subscriptions.models import Suscripcion, PaqueteComprobantes


# ─────────────────────────────────────────────
# Serializers de Empresa
# ─────────────────────────────────────────────

class EmpresaListSerializer(serializers.ModelSerializer):
    """
    Listado general (solo Superadmin).
    Campos suficientes para una tabla/grid sin sobrecargar el payload.
    """
    class Meta:
        model = Empresa
        fields = [
            'id', 'rnc', 'razon_social', 'nombre_comercial',
            'ambiente', 'estado', 'activa', 'creado_at',
        ]
        read_only_fields = fields


class EmpresaDetailSerializer(serializers.ModelSerializer):
    """
    Detalle completo (solo Superadmin).
    Incluye campos de auditoría y certificado (pero NUNCA el storage_key completo en texto plano).
    """
    certificado_vence_pronto = serializers.BooleanField(read_only=True)

    class Meta:
        model = Empresa
        fields = [
            'id', 'rnc', 'razon_social', 'nombre_comercial',
            'ambiente', 'estado', 'activa',
            # Certificado — solo metadatos, nunca el archivo
            'certificado_hash', 'certificado_vence_at', 'certificado_vence_pronto',
            # Auditoría
            'deleted_at', 'creado_at', 'actualizado_at',
        ]
        read_only_fields = fields


class EmpresaWriteSerializer(serializers.ModelSerializer):
    """
    Creación y edición (solo Superadmin).
    Excluye campos de certificado (proceso separado) y auditoría.
    """
    class Meta:
        model = Empresa
        fields = [
            'rnc', 'razon_social', 'nombre_comercial',
            'ambiente', 'estado', 'activa',
        ]

    def validate_rnc(self, value):
        """Valida que el RNC tenga 9 u 11 dígitos."""
        digits = value.replace('-', '')
        if len(digits) not in (9, 11):
            raise serializers.ValidationError("El RNC debe tener 9 u 11 dígitos.")
        return value


class EmpresaAdminSerializer(serializers.ModelSerializer):
    """
    Vista reducida para Admin Empresa (solo lectura).
    NO expone: deleted_at, certificado_hash, certificado_storage_key, actualizado_at.
    """
    certificado_vence_pronto = serializers.BooleanField(read_only=True)

    class Meta:
        model = Empresa
        fields = [
            'id', 'rnc', 'razon_social', 'nombre_comercial',
            'ambiente', 'estado', 'activa',
            'certificado_vence_at', 'certificado_vence_pronto',
            'creado_at',
        ]
        read_only_fields = fields


# ─────────────────────────────────────────────
# Serializers de Suscripción (endpoint /suscripcion/)
# ─────────────────────────────────────────────

class PlanResumenSerializer(serializers.Serializer):
    """Resumen mínimo del plan para mostrar dentro de la suscripción."""
    nombre = serializers.CharField()
    limite_comprobantes = serializers.IntegerField()
    ciclo_disponible = serializers.CharField()


class SuscripcionResumenSerializer(serializers.ModelSerializer):
    """
    Resumen de la suscripción activa de una empresa.
    Disponible para Superadmin y Admin de la empresa.
    """
    plan_detalle = PlanResumenSerializer(source='plan', read_only=True)
    esta_activa = serializers.BooleanField(read_only=True)

    class Meta:
        model = Suscripcion
        fields = [
            'id', 'plan_detalle', 'ciclo', 'estado',
            'fecha_inicio', 'fecha_renovacion',
            'precio_pagado', 'esta_activa',
            'creado_at',
        ]
        read_only_fields = fields


# ─────────────────────────────────────────────
# Serializers de Paquetes (endpoint /comprobantes/)
# ─────────────────────────────────────────────

class PaqueteResumenSerializer(serializers.ModelSerializer):
    """
    Resumen de paquetes de comprobantes de una empresa.
    Disponible para Superadmin y Admin de la empresa.
    """
    comprobantes_restantes = serializers.IntegerField(read_only=True)
    disponible = serializers.BooleanField(read_only=True)

    class Meta:
        model = PaqueteComprobantes
        fields = [
            'id', 'total_comprobantes', 'comprobantes_usados', 'comprobantes_restantes',
            'estado', 'origen', 'fecha_vencimiento', 'disponible',
            'fecha_compra',
        ]
        read_only_fields = fields
