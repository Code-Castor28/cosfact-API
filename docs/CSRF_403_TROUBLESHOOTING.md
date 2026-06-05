# Solución de Error CSRF 403 en Django Admin

## El Problema
Error: **"Prohibido (403) - La verificación CSRF ha fallado"** al acceder a `/admin/login/?next=/admin/`

## Causa Raíz
Django rechaza el token CSRF cuando:
1. El dominio de la cookie CSRF no coincide con el dominio de la solicitud
2. Las variantes HTTP/HTTPS no están sincronizadas en la configuración
3. CSRF_USE_SESSIONS está habilitado pero el token no se valida correctamente

## Soluciones Aplicadas

### 1. ✅ Actualizar `.env`
```bash
# ❌ ANTES (solo HTTPS)
CSRF_TRUSTED_ORIGINS=https://samboxderejfact.derejsoft.com

# ✅ DESPUÉS (ambas variantes)
CSRF_TRUSTED_ORIGINS=https://samboxderejfact.derejsoft.com,http://samboxderejfact.derejsoft.com
```

### 2. ✅ Eliminar configuración hardcodeada de `base.py`
Se eliminó la configuración duplicada que causaba conflictos entre archivos de settings.

### 3. ✅ Hacer `CSRF_COOKIE_DOMAIN` dinámico en `production.py`
Ahora se obtiene automáticamente del primer dominio en `ALLOWED_HOSTS`.

## Pasos de Diagnóstico

### Si el error persiste:

**1. Verificar cookies en el navegador:**
- Abre DevTools (F12) → Application → Cookies
- Busca `csrftoken` o `sessionid`
- Si no ves `csrftoken`, habilita cookies

**2. Habilitar DEBUG para ver el error completo:**
```env
DEBUG=True
```
Esto mostrará el motivo exacto del fallo CSRF.

**3. Verificar el template de login:**
Asegúrate que el formulario incluya el token CSRF:
```html
<form method="post">
    {% csrf_token %}
    <!-- resto del formulario -->
</form>
```

**4. Reiniciar Django después de cambios:**
```bash
python manage.py runserver
```

## Configuración de Producción Recomendada

En tu `.env`:
```env
# Base
ENVIRONMENT=production
DEBUG=False
ALLOWED_HOSTS=samboxderejfact.derejsoft.com,127.0.0.1

# CSRF
CSRF_TRUSTED_ORIGINS=https://samboxderejfact.derejsoft.com,http://samboxderejfact.derejsoft.com

# Optional: si necesitas un dominio personalizado para cookies
SESSION_COOKIE_DOMAIN=samboxderejfact.derejsoft.com
```

## Referencia de Configuración Django CSRF

| Parámetro | Propósito |
|-----------|-----------|
| `ALLOWED_HOSTS` | Dominios aceptados para cualquier solicitud |
| `CSRF_TRUSTED_ORIGINS` | Orígenes que pueden realizar solicitudes CSRF |
| `CSRF_COOKIE_SECURE` | Solo enviar cookie CSRF por HTTPS |
| `SESSION_COOKIE_SECURE` | Solo enviar cookie de sesión por HTTPS |
| `CSRF_COOKIE_DOMAIN` | Dominio para la cookie CSRF (normalmente el dominio principal) |
| `CSRF_USE_SESSIONS` | Guardar token CSRF en la sesión en lugar de en cookie separada |

## Links de Referencia
- [Django CSRF Docs](https://docs.djangoproject.com/en/6.0/ref/csrf/)
- [Django Settings Security](https://docs.djangoproject.com/en/6.0/topics/security/)
