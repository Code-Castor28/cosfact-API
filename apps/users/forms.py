# apps/users/forms.py

from django import forms
from django.contrib.auth.password_validation import validate_password
from .models import Usuario
from empresas.models import Empresa


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'autofocus': True})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput
    )


class CrearUsuarioForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput,
        validators=[validate_password]
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput
    )

    class Meta:
        model = Usuario
        fields = ['email', 'nombre', 'apellido', 'rol', 'empresa']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar roles que no sean SUPERADMIN
        # El superadmin se crea solo desde manage.py createsuperuser
        self.fields['rol'].choices = [
            (Usuario.ROL_ADMIN_EMPRESA, 'Administrador de Empresa'),
            (Usuario.ROL_USUARIO_EMPRESA, 'Usuario de Empresa'),
        ]
        self.fields['empresa'].queryset = Empresa.objects.filter(activa=True)
        self.fields['empresa'].required = True

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError({'password2': 'Las contraseñas no coinciden.'})
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class EditarUsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['nombre', 'apellido', 'rol', 'empresa', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rol'].choices = [
            (Usuario.ROL_ADMIN_EMPRESA, 'Administrador de Empresa'),
            (Usuario.ROL_USUARIO_EMPRESA, 'Usuario de Empresa'),
        ]
        self.fields['empresa'].queryset = Empresa.objects.filter(activa=True)


class CambiarPasswordForm(forms.Form):
    password_actual = forms.CharField(
        label='Contraseña actual',
        widget=forms.PasswordInput
    )
    password_nueva = forms.CharField(
        label='Contraseña nueva',
        widget=forms.PasswordInput,
        validators=[validate_password]
    )
    password_confirmar = forms.CharField(
        label='Confirmar contraseña nueva',
        widget=forms.PasswordInput
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password_nueva')
        p2 = cleaned_data.get('password_confirmar')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError({'password_confirmar': 'Las contraseñas no coinciden.'})
        return cleaned_data