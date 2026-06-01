# PLAN DE EJECUCIÓN — FASE 1 (MVP)

## 📋 ESTADO DE ANÁLISIS PREVIO

- Leídos los 18 archivos de `docs/`
- Explorado todo el proyecto: apps, settings, urls, modelos, views, servicios, migraciones
- Analizada la checklist de DB para e-CF contra modelos existentes
- Analizado documento de verificación arquitectónica
- Analizado el "Manual de Instrucciones Lógicas Completo e Indestructible" del usuario
- Cruzado cada punto del manual contra el código existente
- Resueltas 4 rondas de preguntas de diseño

## 🔗 REFERENCIAS

- **Manual del usuario:** `docs/` (entregado como instrucciones en la conversación)
- **Código existente:** `apps/comprobantes/models.py`, `apps/sequences/models.py`, `apps/empresas/models.py`, `apps/dgii/services.py`, `apps/dgii/utils/xml_builder.py`, `apps/dgii/utils/xml_signer.py`, `apps/empresas/crypto.py`, `apps/api_keys/models.py`
- **Apps vacías (sin implementar):** `apps/comprobantes/` (serializers.py, services.py, urls.py vacíos), `apps/dgii/` (solo modelos y utils), `apps/webhooks/`

---

## 🏗️ BLOQUES DE EJECUCIÓN (orden secuencial)

---

### BLOQUE 0: `apps/comprobantes/models.py` — Correcciones previas a migraciones

**Archivo:** `apps/comprobantes/models.py`

**0.1 Fix `puede_anularse` property (línea ~131):**
```python
# ANTES (INCORRECTO):
@property
def puede_anularse(self):
    return self.estado == self.ESTADO_ACEPTADO

# DESPUÉS (CORRECTO):
@property
def puede_anularse(self):
    return self.estado == self.ESTADO_BORRADOR
```
*Razón: El manual dice "El estado de un comprobante aceptado por la DGII no se puede cambiar a ANULADO. Si se necesita revertir, el sistema exigirá emitir una Nota de Crédito."*

**0.2 Renombrar campo `encf_referencia` → `ncf_modificado`:**
- Operación: migration que renombra el campo
- `comprobante_referencia` FK se mantiene (SET_NULL, null, blank) — ya es opcional

**0.3 Elegir constantes correctas de `TIPOS_ECF` desde `sequences.models`:**
- La migración 0001 tiene labels incorrectos: `(34, 'Nota de Débito')` debe ser `(34, 'Nota de Crédito')`, `(41, 'Nota de Crédito')` debe ser `(41, 'Comprobante de Compras')`
- Se genera nueva migración que altera el campo para corregir los choices
- Se usa `TIPOS_ECF` de `sequences.models` como fuente única de verdad

---

### BLOQUE 1: `apps/empresas/` — Empresa + CertificadoDigital

#### 1.1 Agregar campos a `Empresa`

**Archivo:** `apps/empresas/models.py`

| Campo | Tipo | Detalle |
|-------|------|---------|
| `correo` | `EmailField(blank=True)` | Correo de contacto de la empresa |
| `telefono` | `CharField(max_length=20, blank=True)` | Teléfono de contacto |
| `direccion` | `TextField(blank=True)` | Dirección fiscal completa |

#### 1.2 Crear modelo `CertificadoDigital`

```python
class CertificadoDigital(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.CASCADE,
        related_name="certificados",
    )
    alias = models.CharField(max_length=100, help_text="Nombre descriptivo del certificado")
    archivo = models.FileField(
        upload_to="certificados/",
        help_text="Archivo .p12 del certificado digital",
    )
    pin_cifrado = models.TextField(
        help_text="PIN del certificado cifrado con Fernet (CRYPTOGRAPHY_MASTER_KEY)",
    )
    vigencia_desde = models.DateField()
    vigencia_hasta = models.DateField()
    activo = models.BooleanField(
        default=True,
        help_text="Solo un certificado activo por empresa",
    )
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "certificados_digitales"
        verbose_name = "Certificado Digital"
        verbose_name_plural = "Certificados Digitales"

    def __str__(self):
        return f"{self.alias} — {self.empresa.rnc} {'(activo)' if self.activo else ''}"
```

**Proceso de cifrado del PIN (Flujo):**
1. **Guardado (cifrado):** Cuando el POS/envía el PIN en el request, se llama a:
   ```python
   from empresas.crypto import cifrar
   certificado.pin_cifrado = cifrar(pin_texto_plano)
   certificado.save()
   ```
2. **Uso (descifrado en memoria):** Cuando Celery firma el XML:
   ```python
   from empresas.crypto import descifrar
   pin = descifrar(certificado.pin_cifrado)
   # usar pin, luego descartar (variable sobrescrita)
   ```
3. **Clave maestra:** `settings.FERNET_KEY` (alias de `CRYPTOGRAPHY_MASTER_KEY` en `.env`)

**Migración de datos desde Empresa:**
- Buscar `Empresa` con `certificado_storage_key` no vacío
- Crear `CertificadoDigital` por cada una
- No se migra el PIN (estaba en env vars `CERT_PIN_{empresa.id}`; el usuario lo recargará)

**Admin:**
- `CertificadoDigitalInline` (TabularInline) dentro de `EmpresaAdmin`
- Campos de solo lectura: `pin_cifrado`, `creado_at`

---

### BLOQUE 2: `apps/clientes/` — Nueva app

#### 2.1 Crear estructura de directorios

```
apps/clientes/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── serializers.py
├── tests.py
├── urls.py
└── api/
    ├── __init__.py
    ├── views.py
    └── serializers.py
```

#### 2.2 Modelo `Cliente`

```python
class Cliente(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        "empresas.Empresa",
        on_delete=models.CASCADE,
        related_name="clientes",
    )
    rnc_cedula = models.CharField(max_length=11, db_index=True)
    razon_social = models.CharField(max_length=150)
    direccion = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clientes"
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        unique_together = [("empresa", "rnc_cedula")]

    def __str__(self):
        return f"{self.razon_social} ({self.rnc_cedula})"
```

**Reglas de `rnc_cedula`:**
- Exactamente 11 dígitos numéricos
- No se aceptan guiones ni puntos
- Único por empresa (unique_together)

#### 2.3 Endpoints (API-Key protected)

| Método | URL | Descripción |
|--------|-----|-------------|
| `POST` | `/api/v1/clientes/` | Crear cliente |
| `GET` | `/api/v1/clientes/` | Listar (filtrado por empresa automáticamente) |
| `GET` | `/api/v1/clientes/{rnc_cedula}/` | Detalle por RNC/Cédula |
| `PUT` | `/api/v1/clientes/{rnc_cedula}/` | Actualizar |
| `DELETE` | `/api/v1/clientes/{rnc_cedula}/` | Eliminar |

**Autenticación:**
- Usar `api_keys.authentication.ApiKeyAuthentication` (DRF)
- El usuario autenticado via API-Key es una instancia de `Empresa` (`request.user`)
- Filtrar siempre por `empresa = request.user` para multi-tenant

**Permisos:**
- `rest_framework.permissions.IsAuthenticated` (la ApiKey ya autentica)

**Serializer:**
```python
class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['id', 'rnc_cedula', 'razon_social', 'direccion', 'email',
                  'telefono', 'creado_at', 'actualizado_at']
        read_only_fields = ['id', 'creado_at', 'actualizado_at']

    def validate_rnc_cedula(self, value):
        if not value.isdigit() or len(value) != 11:
            raise serializers.ValidationError(
                "RNC/Cédula debe tener exactamente 11 dígitos numéricos"
            )
        return value
```

**Vista (ViewSet):**
```python
class ClienteViewSet(viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'rnc_cedula'

    def get_queryset(self):
        return Cliente.objects.filter(empresa=self.request.user)

    def perform_create(self, serializer):
        serializer.save(empresa=self.request.user)

    def perform_update(self, serializer):
        serializer.save(empresa=self.request.user)
```

**Router (`core/api_router.py`):**
```python
router.register(r'clientes', ClienteViewSet, basename='cliente')
```

**Admin:**
- Solo lectura (readonly)
- Search fields: `rnc_cedula`, `razon_social`
- List filter: `empresa`

---

### BLOQUE 3: `apps/comprobantes/models.py` — Expansión de campos

#### 3.1 Hacer `rnc_comprador` nullable

```python
# ANTES:
rnc_comprador = models.CharField(max_length=11, blank=True)

# DESPUÉS:
rnc_comprador = models.CharField(max_length=11, blank=True, null=True)
```

#### 3.2 Agregar campos

```python
# --- Nuevos campos planos ---
direccion_comprador = models.CharField(max_length=255, blank=True)

# --- FK a catálogo de clientes (analítica) ---
cliente = models.ForeignKey(
    "clientes.Cliente",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="comprobantes",
)

# --- Montos ---
subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
descuento = models.DecimalField(max_digits=14, decimal_places=2, default=0)

# --- Notas / Observaciones ---
observaciones = models.TextField(blank=True)

# --- Certificado usado para firmar ---
certificado_usado = models.ForeignKey(
    "empresas.CertificadoDigital",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="comprobantes",
)

# --- Campos para Notas E33/E34 (reemplazan encf_referencia) ---
codigo_modificacion = models.PositiveSmallIntegerField(
    null=True,
    blank=True,
    choices=[
        (1, "Anulación"),
        (2, "Texto"),
        (3, "Montos"),
        (4, "Contingencia"),
        (5, "Referencia E32"),
    ],
)
razon_modificacion = models.CharField(max_length=90, blank=True)
```

#### 3.3 Actualizar `clean()` con todas las validaciones

```python
def clean(self):
    errores = {}

    # 1. Rechazar tipos fuera de Fase 1 (MVP)
    if self.tipo_ecf not in {31, 32, 33, 34, 41}:
        raise ValidationError(
            {"tipo_ecf": f"Tipo e-CF {self.tipo_ecf} no soportado en Fase 1. "
                         f"Tipos válidos: 31, 32, 33, 34, 41."}
        )

    # 2. E31 (Crédito Fiscal): RNC/Cédula + Razón Social obligatorios
    if self.tipo_ecf == 31:
        if not self.rnc_comprador:
            errores["rnc_comprador"] = (
                "E31 (Crédito Fiscal) requiere RNC/Cédula del comprador."
            )
        if not self.razon_social_comprador:
            errores["razon_social_comprador"] = (
                "E31 (Crédito Fiscal) requiere Razón Social del comprador."
            )

    # 3. E32 (Consumo): Regla del umbral RD$250,000
    if self.tipo_ecf == 32:
        monto_total = self.monto_total or Decimal("0.00")
        if monto_total >= Decimal("250000.00"):
            if not self.rnc_comprador:
                errores["rnc_comprador"] = (
                    "E32 ≥ RD$250,000 requiere RNC/Cédula del comprador."
                )
        if not self.rnc_comprador:
            # Forzar "CONSUMIDOR FINAL" cuando es anónimo y < 250k
            self.razon_social_comprador = "CONSUMIDOR FINAL"

    # 4. E33/E34 (Notas): Validación de campos de referencia
    if self.tipo_ecf in (33, 34):
        # 4a. Campos obligatorios
        if not self.ncf_modificado:
            errores["ncf_modificado"] = (
                f"E{self.tipo_ecf} requiere el e-NCF del comprobante modificado."
            )
        if not self.codigo_modificacion:
            errores["codigo_modificacion"] = (
                f"E{self.tipo_ecf} requiere código de modificación (1-5)."
            )
        if not self.razon_modificacion:
            errores["razon_modificacion"] = (
                f"E{self.tipo_ecf} requiere razón de la modificación."
            )

        # 4b. Validar que ncf_modificado exista y esté ACEPTADO
        if self.ncf_modificado:
            original = Comprobante.objects.filter(
                encf=self.ncf_modificado,
                estado=Comprobante.ESTADO_ACEPTADO,
            ).first()
            if not original:
                errores["ncf_modificado"] = (
                    f"El e-NCF {self.ncf_modificado} no existe o no está ACEPTADO."
                )
            else:
                # 4c. Validar que el RNC del comprador coincida con el original
                if self.rnc_comprador and original.rnc_comprador:
                    if self.rnc_comprador != original.rnc_comprador:
                        errores["rnc_comprador"] = (
                            "El RNC del comprador de la nota debe coincidir "
                            "con el RNC de la factura original."
                        )

        # 4d. Auto-truncar razon_modificacion a 90 caracteres
        if self.razon_modificacion:
            self.razon_modificacion = self.razon_modificacion[:90]

    # 5. Validación de consistencia de montos (mantener validación existente)
    calculado = self.monto_gravado + self.monto_exento + self.monto_itbis
    if self.monto_total and abs(calculado - self.monto_total) > Decimal("0.01"):
        errores["monto_total"] = (
            f"Monto total ({self.monto_total}) no coincide con "
            f"gravado + exento + ITBIS ({calculado})."
        )

    if errores:
        raise ValidationError(errores)
```

---

### BLOQUE 4: `apps/sequences/` — Sin cambios funcionales

- `obtener_proximo_encf()` se mantiene como está (la API genera e-NCF)
- `Secuencial.proximo_encf()` se mantiene como está
- `TIPOS_ECF` incluye 43-47, pero `Comprobante.clean()` los bloquea en Fase 1
- No se implementa `validar_encf()` (innecesario: la API genera, no valida)

---

### BLOQUE 5: Refactor `apps/dgii/services.py`

#### 5.1 Reemplazar `_get_cert_pin()` para usar `CertificadoDigital`

```python
def _get_cert_pin(empresa: Empresa) -> str:
    """
    Obtiene el PIN del certificado descifrándolo desde CertificadoDigital.
    El PIN se descifra en memoria con Fernet y se descarta tras usarlo.
    """
    from empresas.models import CertificadoDigital
    from empresas.crypto import descifrar

    cert = CertificadoDigital.objects.filter(
        empresa=empresa, activo=True
    ).first()
    if not cert or not cert.pin_cifrado:
        raise ValueError(
            f"No hay certificado activo con PIN para empresa {empresa.rnc}"
        )
    return descifrar(cert.pin_cifrado)
```

#### 5.2 Reemplazar `_cert_path_for_empresa()` para usar `CertificadoDigital.archivo`

```python
def _cert_path_for_empresa(empresa: Empresa) -> str:
    """
    Obtiene la ruta del archivo .p12 desde CertificadoDigital.
    """
    from empresas.models import CertificadoDigital

    cert = CertificadoDigital.objects.filter(
        empresa=empresa, activo=True
    ).first()
    if not cert or not cert.archivo:
        raise ValueError(
            f"No hay certificado activo para empresa {empresa.rnc}"
        )
    return cert.archivo.path
```

#### 5.3 Eliminar

- La función vieja `_get_cert_pin()` que leía de `os.environ.get(f"CERT_PIN_{empresa.id}")`
- La función vieja `_cert_path_for_empresa()` que usaba ruta hardcodeada `/var/derejfact/certificados/`

#### 5.4 El resto de `emitir_ecf()` se mantiene sin cambios

- Genera e-NCF atómicamente
- Construye XML
- Firma con .p12
- Envía a DGII
- Actualiza estado

---

### BLOQUE 6: `core/api_router.py` + `core/urls.py`

#### 6.1 Agregar ClienteViewSet al router

```python
# core/api_router.py
from clientes.api.views import ClienteViewSet

router.register(r'clientes', ClienteViewSet, basename='cliente')
```

#### 6.2 Agregar `clientes` a INSTALLED_APPS

```python
# core/settings/base.py
INSTALLED_APPS = [
    ...
    'clientes',
    ...
]
```

---

### BLOQUE 7: Tests

#### 7.1 `apps/clientes/tests.py`

| Test | Assert |
|------|--------|
| Crear cliente vía API-Key | 201 + datos correctos |
| Crear cliente sin API-Key | 401 |
| Listar clientes (filtro empresa) | Solo clientes de esa empresa |
| Duplicado rnc_cedula misma empresa | 400 |
| Mismo rnc_cedula distinta empresa | OK (201) |
| rnc_cedula no numérico | 400 |
| rnc_cedula != 11 dígitos | 400 |
| Actualizar cliente | 200 + datos actualizados |
| Eliminar cliente | 204 |

#### 7.2 `apps/empresas/tests.py`

| Test | Assert |
|------|--------|
| Crear Empresa con CertificadoDigital | Certificado creado |
| PIN cifrado/descifrado con Fernet | PIN original recuperado |
| Solo un certificado activo por empresa | validar en save/clean |
| Certificado activo consultable desde dgii/services | PIN descifrado correcto |

#### 7.3 `apps/comprobantes/tests.py`

| Test | Assert |
|------|--------|
| E31 sin rnc_comprador | ValidationError |
| E31 sin razon_social_comprador | ValidationError |
| E32 < 250k sin rnc | razon_social = "CONSUMIDOR FINAL" |
| E32 >= 250k sin rnc | ValidationError |
| E33 sin ncf_modificado | ValidationError |
| E33 sin codigo_modificacion | ValidationError |
| E33 sin razon_modificacion | ValidationError |
| E34 con ncf_modificado inexistente | ValidationError |
| E33 con ncf_modificado en estado BORRADOR | ValidationError |
| E33 con RNC diferente al original | ValidationError |
| Tipo 43 | ValidationError "no soportado" |
| Tipo 44 | ValidationError "no soportado" |
| puede_anularse = True cuando BORRADOR | True |
| puede_anularse = False cuando ACEPTADO | False |
| razon_modificacion truncado a 90 | len <= 90 |

---

## 📐 NOTAS DE IMPLEMENTACIÓN

### Redondeo
Usar `Decimal` con `ROUND_HALF_UP` en todos los cálculos matemáticos:
```python
from decimal import Decimal, ROUND_HALF_UP
valor = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

### Fernet / CRYPTOGRAPHY_MASTER_KEY
- Usar `settings.FERNET_KEY` (configurado en `core/settings/base.py:198`)
- En el `.env`: `FERNET_KEY=<valor>` (o `CRYPTOGRAPHY_MASTER_KEY` como alias)
- Funciones existentes en `apps/empresas/crypto.py`: `cifrar()`, `descifrar()`

### Orden de creación de migraciones
1. Bloque 0: renombrar `encf_referencia` → `ncf_modificado`, fix choices
2. Bloque 1: agregar campos a `Empresa`, crear `CertificadoDigital`
3. Bloque 2: crear app `clientes`, modelo `Cliente`
4. Bloque 3: agregar campos a `Comprobante`, hacer `rnc_comprador` nullable
5. Bloque 5: refactor `dgii/services.py` (no requiere migración)

### Dependencias entre migraciones
1. `empresas` (Bloque 1) → no depende de otras
2. `clientes` (Bloque 2) → depende de `empresas`
3. `comprobantes` (Bloque 3) → depende de `empresas`, `clientes`

### Recordatorios de seguridad
- `pin_cifrado` NUNCA se loguea ni se incluye en respuestas API
- El PIN se descifra solo en memoria, se usa y se descarta
- `certificado_storage_key` de `Empresa` queda obsoleto pero no se elimina (datos existentes)
- Si la DB se filtra, el PIN cifrado es inútil sin la `FERNET_KEY`

---

## 📂 ESTRUCTURA FINAL ESPERADA

```
apps/
├── clientes/                    # NUEVA
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── tests.py
│   └── api/
│       ├── __init__.py
│       ├── views.py
│       └── serializers.py
├── comprobantes/
│   └── models.py               # MODIFICADO
├── empresas/
│   ├── models.py               # MODIFICADO
│   └── crypto.py                # EXISTENTE (sin cambios)
├── sequences/
│   └── models.py               # SIN CAMBIOS
└── dgii/
    └── services.py              # MODIFICADO
core/
├── api_router.py                # MODIFICADO
└── settings/
    └── base.py                  # MODIFICADO (INSTALLED_APPS)
```
