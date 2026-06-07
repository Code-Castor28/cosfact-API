from django.contrib import admin
from .catalogs.models import Provincia, Municipio, UnidadMedida, Moneda, ImpuestoAdicional, FormaPago
from .models import DGIILog


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


@admin.register(DGIILog)
class DGIILogAdmin(admin.ModelAdmin):
    list_display = ["empresa", "tipo_operacion", "estado_respuesta", "exitoso", "creado_at"]
    list_filter = ["tipo_operacion", "estado_respuesta", "exitoso", "creado_at"]
    search_fields = ["empresa__rnc", "comprobante__encf"]
    readonly_fields = [f.name for f in DGIILog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
