# apps/users/urls.py

from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Gestión de usuarios (solo SUPERADMIN)
    path('usuarios/', views.lista_usuarios_view, name='lista_usuarios'),
    path('usuarios/crear/', views.crear_usuario_view, name='crear_usuario'),
    path('usuarios/<uuid:usuario_id>/editar/', views.editar_usuario_view, name='editar_usuario'),
    path('usuarios/<uuid:usuario_id>/toggle/', views.toggle_usuario_view, name='toggle_usuario'),

    # Perfil
    path('perfil/', views.perfil_view, name='perfil'),
    path('perfil/password/', views.cambiar_password_view, name='cambiar_password'),
]