from django.contrib import admin
from .models import Plan, Suscripcion, PaqueteComprobantes

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'limite_comprobantes', 'precio_mensual', 'precio_anual', 'activo']
    list_filter = ['activo', 'ciclo_disponible']

@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ['empresa', 'plan', 'ciclo', 'estado', 'fecha_renovacion']
    list_filter = ['estado', 'ciclo']
    search_fields = ['empresa__rnc', 'empresa__razon_social']

@admin.register(PaqueteComprobantes)
class PaqueteAdmin(admin.ModelAdmin):
    list_display = ['empresa', 'plan', 'total_comprobantes', 'comprobantes_usados', 'estado', 'origen']
    list_filter = ['estado', 'origen']
    readonly_fields = ['creado_at']
    search_fields = ['empresa__rnc']