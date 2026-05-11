# apps/users/serializers.py
from rest_framework import serializers
from .models import Usuario
class UsuarioSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(
        source='empresa.razon_social',
        read_only=True
    )

    class Meta:
        model = Usuario
        fields = [
            'id', 'email', 'nombre', 'apellido',
            'rol', 'empresa', 'empresa_nombre',
            'is_active', 'ultimo_login_ip', 'creado_at'
        ]
        read_only_fields = ['id', 'creado_at', 'ultimo_login_ip']