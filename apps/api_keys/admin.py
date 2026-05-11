from django.contrib import admin
from django.contrib import messages
from django.contrib.admin import AdminSite
from django.urls import path
from django.shortcuts import render
from django import forms
from .models import ApiKey
from empresas.models import Empresa


# ─── Formulario ───────────────────────────────────────────────────────────────

class CrearApiKeyForm(forms.Form):
    empresa = forms.ModelChoiceField(
        queryset=Empresa.objects.filter(activa=True),
        label='Empresa'
    )
    nombre = forms.CharField(
        max_length=100,
        label='Nombre descriptivo',
        help_text='Ej: POS Sucursal Norte'
    )
    scopes = forms.MultipleChoiceField(
        choices=[
            ('comprobantes:crear', 'Emitir comprobantes'),
            ('comprobantes:consultar', 'Consultar comprobantes'),
            ('comprobantes:anular', 'Anular comprobantes'),
            ('secuenciales:consultar', 'Consultar secuenciales'),
        ],
        widget=forms.CheckboxSelectMultiple,
        label='Permisos (scopes)'
    )
    allowed_ips = forms.CharField(
        required=False,
        label='IPs permitidas',
        help_text='Una IP o CIDR por línea. Vacío = todas las IPs permitidas.',
        widget=forms.Textarea(attrs={'rows': 3})
    )
    expira_at = forms.DateTimeField(
        required=False,
        label='Fecha de expiración',
        help_text='Dejar vacío si no expira.',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )


# ─── Vista personalizada ──────────────────────────────────────────────────────

def crear_api_key_view(request):
    token_generado = None
    key_creada = None

    if request.method == 'POST':
        form = CrearApiKeyForm(request.POST)
        if form.is_valid():
            empresa = form.cleaned_data['empresa']
            nombre = form.cleaned_data['nombre']
            scopes = form.cleaned_data['scopes']
            allowed_ips_raw = form.cleaned_data['allowed_ips']
            expira_at = form.cleaned_data['expira_at']

            allowed_ips = [
                ip.strip() for ip in allowed_ips_raw.splitlines() if ip.strip()
            ]

            try:
                key, token = ApiKey.crear(
                    empresa=empresa,
                    nombre=nombre,
                    creado_por=request.user,
                    scopes=list(scopes),
                    allowed_ips=allowed_ips,
                    expira_at=expira_at,
                )
                token_generado = token
                key_creada = key
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = CrearApiKeyForm()

    context = {
        **admin.site.each_context(request),
        'title': 'Crear API Key',
        'form': form,
        'token_generado': token_generado,
        'key_creada': key_creada,
        'opts': ApiKey._meta,
    }
    return render(request, 'admin/api_keys/crear_api_key.html', context)


# ─── URL personalizada en el admin ───────────────────────────────────────────

_original_get_urls = AdminSite.get_urls

def _custom_get_urls(self):
    urls = _original_get_urls(self)
    custom = [
        path(
            'api-keys/crear/',
            self.admin_view(crear_api_key_view),
            name='crear_api_key'
        ),
    ]
    return custom + urls

AdminSite.get_urls = _custom_get_urls


# ─── Índice personalizado (agrega el enlace en el dashboard) ─────────────────

_original_index = AdminSite.index

def _custom_index(self, request, extra_context=None):
    extra_context = extra_context or {}
    extra_context['crear_api_key_url'] = '/admin/api-keys/crear/'
    return _original_index(self, request, extra_context)

AdminSite.index = _custom_index


# ─── Registro en el admin ────────────────────────────────────────────────────

@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 'empresa', 'prefix', 'activa',
        'rate_limit_cantidad', 'rate_limit_ventana',
        'ultimo_uso_at', 'creado_at'
    ]
    list_filter = ['activa', 'rate_limit_ventana']
    search_fields = ['empresa__rnc', 'nombre', 'prefix']
    readonly_fields = [
        'prefix', 'key_hash', 'creado_at', 'actualizado_at',
        'revocado_at', 'revocado_por', 'revocado_motivo',
        'ultimo_uso_at', 'ultimo_uso_ip'
    ]

    def has_add_permission(self, request):
        return False

    def revocar_keys(self, request, queryset):
        revocadas = 0
        for key in queryset.filter(activa=True):
            key.revocar(revocado_por=request.user, motivo='Revocada desde el admin')
            revocadas += 1
        self.message_user(request, f'{revocadas} API Key(s) revocadas.', messages.SUCCESS)

    revocar_keys.short_description = 'Revocar API Keys seleccionadas'
    actions = ['revocar_keys']