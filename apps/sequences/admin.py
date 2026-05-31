from django.contrib import admin
from .models import Secuencial, MovimientoSecuencial

@admin.register(Secuencial)
class SecuencialAdmin(admin.ModelAdmin):
    list_display = ['empresa', 'tipo_ecf', 'ultimo_numero', 'maximo_asignado', 'porcentaje_uso_display', 'bloqueado', 'casi_agotado']
    list_filter = ['tipo_ecf', 'bloqueado']
    search_fields = ['empresa__rnc']
    readonly_fields = ['creado_at', 'actualizado_at', 'fecha_bloqueo', 'usuario_bloqueo']

    def casi_agotado(self, obj):
        return obj.casi_agotado
    casi_agotado.boolean = True

    def porcentaje_uso_display(self, obj):
        return f"{obj.porcentaje_uso:.1f}%"
    porcentaje_uso_display.short_description = "% Uso"


@admin.register(MovimientoSecuencial)
class MovimientoSecuencialAdmin(admin.ModelAdmin):
    list_display = ['encf_generado', 'empresa', 'tipo_ecf', 'comprobante', 'creado_at']
    list_filter = ['tipo_ecf', 'creado_at']
    search_fields = ['encf_generado', 'empresa__rnc']
    readonly_fields = ['creado_at']