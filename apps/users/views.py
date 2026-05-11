# apps/users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from functools import wraps
from .models import Usuario
from .forms import LoginForm, CrearUsuarioForm, EditarUsuarioForm, CambiarPasswordForm


# ─── Decoradores de rol ───────────────────────────────────────────────────────

def superadmin_required(view_func):
    @wraps(view_func)
    @login_required(login_url='users:login')
    def wrapper(request, *args, **kwargs):
        if request.user.rol != Usuario.ROL_SUPERADMIN:
            messages.error(request, 'No tienes permiso para acceder a esta sección.')
            return redirect('users:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_requerido(view_func):
    return login_required(login_url='users:login')(view_func)


# ─── Login / Logout ───────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('users:dashboard')

    form = LoginForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']

        try:
            usuario = Usuario.objects.get(email=email)
        except Usuario.DoesNotExist:
            messages.error(request, 'Credenciales incorrectas.')
            return render(request, 'users/login.html', {'form': form})

        if usuario.esta_bloqueado():
            messages.error(
                request,
                f'Cuenta bloqueada por múltiples intentos fallidos. '
                f'Intenta de nuevo después de las {usuario.bloqueado_hasta.strftime("%H:%M")}.'
            )
            return render(request, 'users/login.html', {'form': form})

        user = authenticate(request, username=email, password=password)

        if user is None:
            usuario.registrar_intento_fallido()
            intentos_restantes = max(0, 5 - usuario.intentos_fallidos)
            messages.error(
                request,
                f'Credenciales incorrectas. '
                f'Intentos restantes: {intentos_restantes}'
            )
            return render(request, 'users/login.html', {'form': form})

        if not user.is_active:
            messages.error(request, 'Tu cuenta está desactivada. Contacta al administrador.')
            return render(request, 'users/login.html', {'form': form})

        # Login exitoso
        user.limpiar_intentos()
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR', '')
        )
        user.ultimo_login_ip = ip
        user.save(update_fields=['ultimo_login_ip'])

        login(request, user)
        return redirect('users:dashboard')

    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('users:login')


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_requerido
def dashboard_view(request):
    context = {'usuario': request.user}

    if request.user.rol == Usuario.ROL_SUPERADMIN:
        from empresas.models import Empresa
        from comprobantes.models import Comprobante
        context['total_empresas'] = Empresa.objects.filter(activa=True).count()
        context['total_usuarios'] = Usuario.objects.filter(is_active=True).count()
        context['total_comprobantes'] = Comprobante.objects.count()
        context['empresas_recientes'] = Empresa.objects.order_by('-creado_at')[:5]
        return render(request, 'users/dashboard_superadmin.html', context)

    else:
        empresa = request.user.empresa
        from comprobantes.models import Comprobante
        from api_keys.models import ApiKey
        from subscriptions.models import PaqueteComprobantes

        context['empresa'] = empresa
        context['comprobantes_recientes'] = (
            Comprobante.objects.filter(empresa=empresa).order_by('-creado_at')[:10]
        )
        context['api_keys'] = ApiKey.objects.filter(empresa=empresa, activa=True)
        context['paquete_activo'] = (
            PaqueteComprobantes.objects.filter(empresa=empresa, estado='ACTIVO').first()
        )
        return render(request, 'users/dashboard_empresa.html', context)


# ─── Gestión de usuarios (solo SUPERADMIN) ────────────────────────────────────

@superadmin_required
def lista_usuarios_view(request):
    usuarios = Usuario.objects.select_related('empresa').exclude(
        rol=Usuario.ROL_SUPERADMIN
    ).order_by('empresa__razon_social', 'nombre')
    return render(request, 'users/lista_usuarios.html', {'usuarios': usuarios})


@superadmin_required
def crear_usuario_view(request):
    form = CrearUsuarioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Usuario creado correctamente.')
        return redirect('users:lista_usuarios')
    return render(request, 'users/crear_usuario.html', {'form': form})


@superadmin_required
def editar_usuario_view(request, usuario_id):
    usuario = get_object_or_404(
        Usuario.objects.exclude(rol=Usuario.ROL_SUPERADMIN),
        id=usuario_id
    )
    form = EditarUsuarioForm(request.POST or None, instance=usuario)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Usuario actualizado correctamente.')
        return redirect('users:lista_usuarios')
    return render(request, 'users/editar_usuario.html', {'form': form, 'usuario': usuario})


@superadmin_required
def toggle_usuario_view(request, usuario_id):
    usuario = get_object_or_404(
        Usuario.objects.exclude(rol=Usuario.ROL_SUPERADMIN),
        id=usuario_id
    )
    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=['is_active'])
    estado = 'activado' if usuario.is_active else 'desactivado'
    messages.success(request, f'Usuario {estado} correctamente.')
    return redirect('users:lista_usuarios')


# ─── Perfil propio ────────────────────────────────────────────────────────────

@login_requerido
def perfil_view(request):
    return render(request, 'users/perfil.html', {'usuario': request.user})


@login_requerido
def cambiar_password_view(request):
    form = CambiarPasswordForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        usuario = request.user

        if not usuario.check_password(form.cleaned_data['password_actual']):
            messages.error(request, 'La contraseña actual es incorrecta.')
            return render(request, 'users/cambiar_password.html', {'form': form})

        usuario.set_password(form.cleaned_data['password_nueva'])
        usuario.save()
        # Volver a hacer login para no perder la sesión
        login(request, usuario)
        messages.success(request, 'Contraseña actualizada correctamente.')
        return redirect('users:perfil')

    return render(request, 'users/cambiar_password.html', {'form': form})