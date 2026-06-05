from rest_framework import serializers
from .catalogs.models import (
    Provincia, Municipio, UnidadMedida, Moneda,
    ImpuestoAdicional, FormaPago,
)


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
