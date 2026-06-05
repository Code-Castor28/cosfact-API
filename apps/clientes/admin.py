from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['rnc_cedula', 'razon_social', 'empresa', 'email', 'telefono', 'creado_at']
    list_filter = ['empresa']
    search_fields = ['rnc_cedula', 'razon_social', 'email']
    readonly_fields = ['id', 'creado_at', 'actualizado_at']
