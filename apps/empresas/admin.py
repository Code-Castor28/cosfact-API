from django.contrib import admin
from .models import Empresa, TokenDGII
from .notifications import Notificacion

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ['rnc', 'razon_social', 'ambiente', 'estado', 'activa', 'certificado_vence_at']
    list_filter = ['ambiente', 'estado', 'activa']
    search_fields = ['rnc', 'razon_social']
    readonly_fields = ['id', 'creado_at', 'actualizado_at', 'deleted_at']

@admin.register(TokenDGII)
class TokenDGIIAdmin(admin.ModelAdmin):
    list_display = ['empresa', 'ambiente', 'activo', 'expira_at']
    list_filter = ['ambiente', 'activo']
    readonly_fields = ['creado_at']

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['empresa', 'tipo', 'nivel', 'titulo', 'leida', 'creado_at']
    list_filter = ['nivel', 'tipo', 'leida']
    readonly_fields = ['creado_at']