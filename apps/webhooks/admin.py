from django.contrib import admin
from .models import Webhook, WebhookEntrega


class WebhookEntregaInline(admin.TabularInline):
    model = WebhookEntrega
    fields = ["evento", "estado", "intentos", "ultimo_http_status", "creado_at"]
    readonly_fields = fields
    can_delete = False
    show_change_link = True
    extra = 0


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ["nombre", "empresa", "url", "estado", "activo", "ultimo_intento_at"]
    list_filter = ["estado", "activo", "empresa"]
    search_fields = ["nombre", "url"]
    readonly_fields = ["id", "secret_hash", "ultimo_intento_at", "ultimo_http_status"]
    inlines = [WebhookEntregaInline]


@admin.register(WebhookEntrega)
class WebhookEntregaAdmin(admin.ModelAdmin):
    list_display = ["evento", "webhook", "estado", "intentos", "ultimo_http_status", "creado_at"]
    list_filter = ["estado", "evento"]
    search_fields = ["webhook__nombre", "webhook__url"]
    readonly_fields = [f.name for f in WebhookEntrega._meta.fields]
