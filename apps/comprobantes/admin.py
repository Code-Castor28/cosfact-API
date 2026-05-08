from django.contrib import admin
from .models import Comprobante, ComprobanteDetalle, ComprobanteEvento

class DetalleInline(admin.TabularInline):
    model = ComprobanteDetalle
    extra = 0
    readonly_fields = ['subtotal']

class EventoInline(admin.TabularInline):
    model = ComprobanteEvento
    extra = 0
    readonly_fields = ['estado_anterior', 'estado_nuevo', 'mensaje', 'creado_at']
    can_delete = False

@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_display = ['encf', 'empresa', 'tipo_ecf', 'monto_total', 'estado', 'fecha_emision']
    list_filter = ['estado', 'tipo_ecf', 'empresa']
    search_fields = ['encf', 'empresa__rnc', 'rnc_comprador']
    readonly_fields = [
        'id', 'encf', 'rnc_emisor', 'codigo_seguridad_dgii',
        'track_id_dgii', 'xml_hash', 'creado_at', 'actualizado_at'
    ]
    inlines = [DetalleInline, EventoInline]