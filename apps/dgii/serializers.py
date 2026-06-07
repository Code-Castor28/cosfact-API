from rest_framework import serializers
from .catalogs.models import (
    Provincia, Municipio, UnidadMedida, Moneda,
    ImpuestoAdicional, FormaPago,
)
from .models import DGIILog


class ProvinciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provincia
        fields = ["codigo", "nombre"]


class MunicipioSerializer(serializers.ModelSerializer):
    provincia_nombre = serializers.CharField(source="provincia.nombre", read_only=True)

    class Meta:
        model = Municipio
        fields = ["codigo", "provincia", "provincia_nombre", "nombre"]


class UnidadMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadMedida
        fields = ["codigo", "abreviatura", "nombre"]


class MonedaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Moneda
        fields = ["codigo_iso", "nombre"]


class ImpuestoAdicionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImpuestoAdicional
        fields = ["codigo", "nombre", "descripcion", "tipo", "tasa"]


class FormaPagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormaPago
        fields = ["codigo", "nombre"]


class DGIILogSerializer(serializers.ModelSerializer):
    empresa_rnc = serializers.CharField(source="empresa.rnc", read_only=True)
    comprobante_encf = serializers.CharField(source="comprobante.encf", read_only=True, allow_null=True)
    tipo_operacion_display = serializers.CharField(source="get_tipo_operacion_display", read_only=True)

    class Meta:
        model = DGIILog
        fields = [
            "id", "empresa", "empresa_rnc",
            "comprobante", "comprobante_encf",
            "ambiente", "tipo_operacion", "tipo_operacion_display",
            "endpoint", "http_status",
            "estado_respuesta", "codigo_dgii", "mensaje_dgii",
            "respuesta_raw", "exitoso", "codigo_error", "mensaje",
            "duracion_ms", "celery_task_id",
            "creado_at",
        ]
        read_only_fields = fields
