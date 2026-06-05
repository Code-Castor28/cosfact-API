# apps/users/serializers.py
from rest_framework import serializers
from core.serializers import CleanModelSerializer
from .models import Usuario
from empresas.models import Empresa

class EmpresaMiniSerializer(CleanModelSerializer):
    class Meta:
        model = Empresa
        fields = ['id', 'razon_social', 'rnc']

class UsuarioSerializer(CleanModelSerializer):
    empresa_detalle = EmpresaMiniSerializer(source='empresa', read_only=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Usuario
        fields = [
            'id', 'email', 'nombre', 'apellido',
            'rol', 'empresa', 'empresa_detalle',
            'password', 'is_active', 'creado_at'
        ]
        read_only_fields = ['id', 'creado_at']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        
        # Agregar campos sensibles solo si es SUPERADMIN
        if request and request.user and request.user.rol == 'SUPERADMIN':
            fields['intentos_fallidos'] = serializers.IntegerField(read_only=True)
            fields['bloqueado_hasta'] = serializers.DateTimeField(read_only=True)
            fields['ultimo_login_ip'] = serializers.CharField(read_only=True)
            
        return fields

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        # La validación de que un no-superadmin necesita empresa está en el clean() del modelo
        # o la podemos forzar aquí, pero UserManager.create_user maneja lo básico
        user = Usuario.objects.create_user(password=password, **validated_data)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        return super().update(instance, validated_data)


class CambiarPasswordSerializer(serializers.Serializer):
    password_actual = serializers.CharField(required=True)
    password_nueva = serializers.CharField(required=True)