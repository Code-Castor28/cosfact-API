from django.contrib import admin
from .catalogs.models import Provincia, Municipio, UnidadMedida, Moneda, ImpuestoAdicional, FormaPago


@admin.register(Provincia)
class ProvinciaAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre"]
    search_fields = ["nombre", "codigo"]


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "provincia"]
    list_filter = ["provincia"]
    search_fields = ["nombre", "codigo"]


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ["codigo", "abreviatura", "nombre"]
    search_fields = ["nombre", "abreviatura"]


@admin.register(Moneda)
class MonedaAdmin(admin.ModelAdmin):
    list_display = ["codigo_iso", "nombre"]
    search_fields = ["nombre", "codigo_iso"]


@admin.register(ImpuestoAdicional)
class ImpuestoAdicionalAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "tipo", "tasa"]
    list_filter = ["tipo"]
    search_fields = ["nombre", "codigo", "descripcion"]


@admin.register(FormaPago)
class FormaPagoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre"]
    search_fields = ["nombre"]
