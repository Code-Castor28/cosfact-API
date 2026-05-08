from django.contrib import admin
from .models import Secuencial

@admin.register(Secuencial)
class SecuencialAdmin(admin.ModelAdmin):
    list_display = ['empresa', 'tipo_ecf', 'ultimo_numero', 'maximo_asignado', 'bloqueado', 'casi_agotado']
    list_filter = ['tipo_ecf', 'bloqueado']
    search_fields = ['empresa__rnc']
    readonly_fields = ['creado_at', 'actualizado_at']

    def casi_agotado(self, obj):
        return obj.casi_agotado
    casi_agotado.boolean = True