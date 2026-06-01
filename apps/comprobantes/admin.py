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
        'track_id_dgii', 'xml_hash', 'subtotal', 'descuento',
        'creado_at', 'actualizado_at',
    ]
    fieldsets = (
        (None, {
            'fields': ('empresa', 'tipo_ecf', 'encf', 'estado')
        }),
        ('Receptor', {
            'fields': ('rnc_comprador', 'cedula_comprador',
                       'razon_social_comprador', 'direccion_comprador', 'cliente')
        }),
        ('Montos', {
            'fields': ('subtotal', 'descuento', 'monto_gravado',
                       'monto_exento', 'monto_itbis', 'monto_total')
        }),
        ('Notas E33/E34', {
            'fields': ('ncf_modificado', 'codigo_modificacion',
                       'razon_modificacion'),
            'classes': ('collapse',),
        }),
        ('DGII', {
            'fields': ('track_id_dgii', 'codigo_seguridad_dgii',
                       'xml_path', 'xml_hash', 'xml_version'),
        }),
        ('Metadata', {
            'fields': ('idempotency_key', 'paquete', 'certificado_usado',
                       'observaciones', 'intentos_envio', 'ultimo_error',
                       'fecha_emision', 'fecha_vencimiento_pago', 'condicion_pago',
                       'creado_at', 'actualizado_at'),
        }),
    )
    inlines = [DetalleInline, EventoInline]