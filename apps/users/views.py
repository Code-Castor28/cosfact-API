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
        from empresas.models import Empresa, TokenDGII
        from comprobantes.models import Comprobante
        from subscriptions.models import Suscripcion, PaqueteComprobantes
        from django.utils import timezone
        from django.db.models import Count, Sum, Q
        import datetime

        hoy = timezone.now().date()
        inicio_mes = hoy.replace(day=1)
        inicio_semana = hoy - datetime.timedelta(days=hoy.weekday())
        hace_30_dias = hoy - datetime.timedelta(days=30)

        # ── KPIs generales ────────────────────────────────────────────────────
        total_empresas = Empresa.objects.filter(activa=True, deleted_at__isnull=True).count()
        total_usuarios = Usuario.objects.filter(is_active=True).exclude(rol=Usuario.ROL_SUPERADMIN).count()
        usuarios_bloqueados = Usuario.objects.filter(
            bloqueado_hasta__gt=timezone.now()
        ).count()

        # ── Comprobantes ──────────────────────────────────────────────────────
        total_comprobantes = Comprobante.objects.count()
        comprobantes_hoy = Comprobante.objects.filter(creado_at__date=hoy).count()
        comprobantes_semana = Comprobante.objects.filter(creado_at__date__gte=inicio_semana).count()
        comprobantes_mes = Comprobante.objects.filter(creado_at__date__gte=inicio_mes).count()
        comprobantes_aceptados = Comprobante.objects.filter(estado='ACEPTADO').count()
        comprobantes_rechazados = Comprobante.objects.filter(estado='RECHAZADO').count()
        comprobantes_error = Comprobante.objects.filter(estado='ERROR').count()
        comprobantes_contingencia = Comprobante.objects.filter(estado='CONTINGENCIA').count()

        tasa_aceptacion = 0
        if total_comprobantes > 0:
            tasa_aceptacion = round((comprobantes_aceptados / total_comprobantes) * 100, 1)

        # ── Salud del sistema (alertas críticas) ──────────────────────────────
        vence_en_30 = hoy + datetime.timedelta(days=30)
        empresas_cert_venciendo = Empresa.objects.filter(
            activa=True,
            certificado_vence_at__lte=vence_en_30,
            certificado_vence_at__gte=hoy,
        ).count()

        empresas_cert_vencido = Empresa.objects.filter(
            activa=True,
            certificado_vence_at__lt=hoy,
        ).count()

        empresas_token_expirado = TokenDGII.objects.filter(
            activo=True,
            expira_at__lt=timezone.now(),
        ).values('empresa').distinct().count()

        empresas_sin_paquete = Empresa.objects.filter(
            activa=True,
            deleted_at__isnull=True,
        ).exclude(
            paquetes__estado='ACTIVO'
        ).count()

        # ── Monetización ──────────────────────────────────────────────────────
        suscripciones_activas = Suscripcion.objects.filter(estado='ACTIVA').count()
        suscripciones_vencidas = Suscripcion.objects.filter(estado='VENCIDA').count()

        # ── Gráfica: emisiones por día últimos 14 días ─────────────────────
        hace_14_dias = hoy - datetime.timedelta(days=13)
        emisiones_por_dia = (
            Comprobante.objects
            .filter(creado_at__date__gte=hace_14_dias)
            .values('creado_at__date')
            .annotate(total=Count('id'))
            .order_by('creado_at__date')
        )
        # Construir lista completa de 14 días (con ceros para días sin emisiones)
        dias_map = {e['creado_at__date']: e['total'] for e in emisiones_por_dia}
        grafica_labels = []
        grafica_data = []
        for i in range(14):
            dia = hace_14_dias + datetime.timedelta(days=i)
            grafica_labels.append(dia.strftime('%d/%m'))
            grafica_data.append(dias_map.get(dia, 0))

        # ── Gráfica: comprobantes por estado (pie) ────────────────────────
        pie_labels = ['Aceptados', 'Rechazados', 'Pendientes', 'Error', 'Contingencia']
        pie_data = [
            comprobantes_aceptados,
            comprobantes_rechazados,
            Comprobante.objects.filter(estado__in=['PENDIENTE', 'PROCESANDO']).count(),
            comprobantes_error,
            comprobantes_contingencia,
        ]

        # ── Alertas críticas ──────────────────────────────────────────────
        alertas = []
        if empresas_cert_vencido > 0:
            alertas.append({
                'nivel': 'critico',
                'mensaje': f'{empresas_cert_vencido} empresa(s) con certificado digital VENCIDO.'
            })
        if empresas_cert_venciendo > 0:
            alertas.append({
                'nivel': 'advertencia',
                'mensaje': f'{empresas_cert_venciendo} empresa(s) con certificado a vencer en 30 días.'
            })
        if empresas_token_expirado > 0:
            alertas.append({
                'nivel': 'advertencia',
                'mensaje': f'{empresas_token_expirado} empresa(s) con token DGII expirado.'
            })
        if empresas_sin_paquete > 0:
            alertas.append({
                'nivel': 'info',
                'mensaje': f'{empresas_sin_paquete} empresa(s) sin paquete de comprobantes activo.'
            })

        # ── Top 5 empresas por emisiones ──────────────────────────────────
        top_empresas = (
            Comprobante.objects
            .filter(creado_at__date__gte=hace_30_dias)
            .values('empresa__razon_social', 'empresa__rnc')
            .annotate(total=Count('id'))
            .order_by('-total')[:5]
        )

        # ── Últimos usuarios registrados ──────────────────────────────────
        ultimos_usuarios = (
            Usuario.objects
            .exclude(rol=Usuario.ROL_SUPERADMIN)
            .select_related('empresa')
            .order_by('-creado_at')[:5]
        )

        context.update({
            # KPIs
            'total_empresas': total_empresas,
            'total_usuarios': total_usuarios,
            'usuarios_bloqueados': usuarios_bloqueados,
            'total_comprobantes': total_comprobantes,
            'comprobantes_hoy': comprobantes_hoy,
            'comprobantes_semana': comprobantes_semana,
            'comprobantes_mes': comprobantes_mes,
            'tasa_aceptacion': tasa_aceptacion,
            'comprobantes_rechazados': comprobantes_rechazados,
            'comprobantes_error': comprobantes_error,
            'comprobantes_contingencia': comprobantes_contingencia,
            # Salud
            'empresas_cert_venciendo': empresas_cert_venciendo,
            'empresas_cert_vencido': empresas_cert_vencido,
            'empresas_token_expirado': empresas_token_expirado,
            'empresas_sin_paquete': empresas_sin_paquete,
            # Monetización
            'suscripciones_activas': suscripciones_activas,
            'suscripciones_vencidas': suscripciones_vencidas,
            # Gráficas
            'grafica_labels': grafica_labels,
            'grafica_data': grafica_data,
            'pie_labels': pie_labels,
            'pie_data': pie_data,
            # Tablas
            'top_empresas': top_empresas,
            'ultimos_usuarios': ultimos_usuarios,
            'alertas': alertas,
            'empresas_recientes': Empresa.objects.filter(
                deleted_at__isnull=True
            ).order_by('-creado_at')[:5],
        })

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
