from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ['email', 'nombre', 'apellido', 'rol', 'empresa', 'is_active']
    list_filter = ['rol', 'is_active']
    search_fields = ['email', 'nombre', 'apellido']
    ordering = ['email']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Información personal', {'fields': ('nombre', 'apellido', 'empresa', 'rol')}),
        ('Seguridad', {'fields': ('intentos_fallidos', 'bloqueado_hasta', 'ultimo_login_ip')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre', 'apellido', 'rol', 'empresa', 'password1', 'password2'),
        }),
    )