from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "creado_at",
        "accion",
        "recurso",
        "recurso_id",
        "empresa",
        "usuario",
        "api_key_prefix",
        "response_status",
    ]
    list_filter = ["accion", "empresa", "response_status"]
    search_fields = ["recurso", "recurso_id", "endpoint", "api_key_prefix"]
    readonly_fields = [
        "empresa",
        "usuario",
        "api_key_prefix",
        "accion",
        "recurso",
        "recurso_id",
        "endpoint",
        "metodo_http",
        "ip",
        "ip_pais",
        "user_agent",
        "request_body_hash",
        "response_status",
        "extra",
        "creado_at",
        "signature",
    ]
    ordering = ["-creado_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
