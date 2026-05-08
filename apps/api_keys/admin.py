from django.contrib import admin
from .models import ApiKey

@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'empresa', 'prefix', 'activa', 'ultimo_uso_at', 'creado_at']
    list_filter = ['activa']
    search_fields = ['empresa__rnc', 'nombre', 'prefix']
    readonly_fields = ['prefix', 'key_hash', 'creado_at', 'revocado_at', 'revocado_por', 'ultimo_uso_at']