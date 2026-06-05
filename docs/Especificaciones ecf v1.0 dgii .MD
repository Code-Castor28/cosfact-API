# Especificaciones Técnicas — Software de Facturación Electrónica
## Formato e-CF Versión 1.0 | DGII República Dominicana

---

## 1. Tipos de Comprobantes Fiscales Electrónicos (e-CF)

| Código | Tipo | Uso |
|:---:|:---|:---|
| 31 | Factura de Crédito Fiscal Electrónica | Operaciones con derecho a crédito fiscal |
| 32 | Factura de Consumo Electrónica | Operaciones con consumidores finales |
| 33 | Nota de Débito Electrónica | Incremento del monto facturado |
| 34 | Nota de Crédito Electrónica | Disminución, anulaciones o correcciones |
| 41 | Compras Electrónico | Registro de compras realizadas |
| 43 | Gastos Menores Electrónico | Gastos menores sin derecho a crédito fiscal |
| 44 | Regímenes Especiales Electrónico | Contribuyentes en regímenes especiales |
| 45 | Gubernamental Electrónico | Operaciones con el Estado |
| 46 | Comprobante de Exportaciones Electrónico | Operaciones de exportación |
| 47 | Comprobante para Pagos al Exterior Electrónico | Pagos a proveedores en el exterior |

---

## 2. Estructura Obligatoria del e-CF

8 secciones en orden fijo:

| Orden | Sección | Tag XML | Obligatoriedad |
|:---:|:---|:---|:---:|
| 1 | Encabezado | `<Encabezado>` | Siempre |
| 2 | Detalle de Bienes o Servicios | `<DetallesItem>` | Siempre |
| 3 | Subtotales Informativos | `<Subtotales>` | Opcional |
| 4 | Descuentos o Recargos | `<DescuentosORecargos>` | Condicional |
| 5 | Paginación | `<Paginacion>` | Condicional |
| 6 | Información de Referencia | `<InformacionReferencia>` | Condicional |
| 7 | Fecha y Hora de la Firma Digital | `<FechaHoraFirma>` | Siempre |
| 8 | Firma Digital | `<Signature>` | Siempre |

---

## 3. Códigos de Obligatoriedad

| Código | Nombre | Significado |
|:---:|:---|:---|
| 0 | No corresponde | El dato NO debe incluirse |
| 1 | Obligatorio | Siempre debe estar presente |
| 2 | Condicional | Obligatorio solo si se cumple una condición |
| 3 | Opcional | A criterio del emisor |

---

## 4. Encabezado — Campos Obligatorios

### 4.1 Versión y Documento

| Campo | Tag XML | Tipo | Largo | Valor |
|:---|:---|:---:|:---:|:---|
| Versión | `<Version>` | ALFANUM | 3 | "1.0" |
| Tipo e-CF | `<TipoECF>` | NUM | 2 | 31,32,33,34,41,43,44,45,46,47 |
| e-NCF | `<eNCF>` | ALFANUM | 13 | Secuencia autorizada por DGII |
| Fecha Emisión | `<FechaEmision>` | ALFANUM | 10 | Formato dd-MM-AAAA |

### 4.2 Emisor

| Campo | Tag XML | Tipo | Largo |
|:---|:---|:---:|:---:|
| RNC Emisor | `<RNCEmisor>` | NUM | 9 u 11 |
| Nombre o Razón Social | `<RazonSocialEmisor>` | ALFANUM | 150 |
| Dirección Emisor | `<DireccionEmisor>` | ALFANUM | 100 |

### 4.3 Totales

| Campo | Tag XML | Validación |
|:---|:---|:---|
| Monto Total | `<MontoTotal>` | 16 enteros, 2 decimales; ≥ 0 |
| Monto Gravado Total | `<MontoGravadoTotal>` | Condicional a que existan montos gravados |
| Total ITBIS | `<TotalITBIS>` | Condicional a que exista ITBIS |

### 4.4 Firma Digital

| Campo | Tag XML | Formato |
|:---|:---|:---|
| Fecha y Hora Firma | `<FechaHoraFirma>` | dd-MM-AAAA HH:mm:ss — Zona GMT -4 |
| Firma Digital | `<Signature>` | Sobre todo el documento |

---

## 5. Encabezado — Campos Condicionales

| Campo | Tag XML | Condición |
|:---|:---|:---|
| RNC Comprador | `<RNCComprador>` | e-CF tipo 32 con monto ≥ DOP$250,000 |
| Identificador Extranjero | `<IdentificadorExtranjero>` | Comprador extranjero sin RNC/Cédula |
| Indicador Envío Diferido | `<IndicadorEnvíoDiferido>` | Autorizado por DGII para ventas offline |
| Fecha Límite de Pago | `<FechaLimitePago>` | Tipo de Pago = 2 (Crédito) |
| Forma de Pago | `<FormaPago>` | Si existe forma de pago definida |
| Monto de Pago | `<MontoPago>` | Si existe forma de pago |
| Información de Referencia | `<InformacionReferencia>` | Nota de Crédito/Débito o reemplazo |

---

## 6. Detalle de Bienes o Servicios

### 6.1 Campos obligatorios por ítem

| Campo | Tag XML | Tipo | Largo | Validación |
|:---|:---|:---:|:---:|:---|
| N° de Línea | `<NumeroLinea>` | NUM | 5 | Secuencial desde 1 |
| Indicador de Facturación | `<IndicadorFacturacion>` | NUM | 1 | 0,1,2,3,4 |
| Nombre del Ítem | `<NombreItem>` | ALFANUM | 80 | — |
| Cantidad | `<CantidadItem>` | NUM | 18 | 16 enteros, 2 decimales; > 0 |
| Precio Unitario | `<PrecioUnitarioItem>` | NUM | 20 | 16 enteros, 4 decimales; ≥ 0 |
| Monto Ítem | `<MontoItem>` | NUM | 18 | (Precio × Cantidad) - Descuento + Recargo |

### 6.2 Indicador de Facturación

| Valor | Significado | Tasa ITBIS |
|:---:|:---|:---:|
| 0 | No Facturable | N/A |
| 1 | Gravado ITBIS Tasa 1 | 18% |
| 2 | Gravado ITBIS Tasa 2 | 16% |
| 3 | Gravado ITBIS Tasa 3 | 0% |
| 4 | Exento | N/A |

### 6.3 Límites de líneas por tipo de e-CF

| Tipo e-CF | Condición | Máximo de líneas |
|:---:|:---|:---:|
| 32 | Monto ≥ DOP$250,000 | 1,000 |
| 32 | Monto < DOP$250,000 | 10,000 |
| Todos los demás | Cualquier monto | 100 |

---

## 7. Fórmulas de Validación de Totales

```
MontoGravadoTotal = MontoGravado1 + MontoGravado2 + MontoGravado3

TotalITBIS = TotalITBIS1 + TotalITBIS2 + TotalITBIS3

MontoTotal = MontoGravadoTotal + MontoExento + TotalITBIS + MontoImpuestoAdicional

ValorPagar = MontoTotal - MontoAvancePago ± SaldoAnterior
```

Si `IndicadorMontoGravado = 1` (monto incluye ITBIS):
```
MontoGravado1 = Suma(MontoItem con indicador=1) / (1 + 0.18)
```

Validación Notas de Crédito:
```
MontoTotal (Nota Crédito) ≤ MontoTotal (e-CF modificado)
```

Validación Paginación:
```
MontoTotal = Suma(MontoSubtotalPagina) para todas las páginas
```

---

## 8. Máximo de Repeticiones por Sección

| Sección / Elemento | Máximo |
|:---|:---:|
| Ítems en Detalle (excepto tipo 32) | 100 |
| Ítems en Detalle (tipo 32, monto ≥ DOP$250,000) | 1,000 |
| Ítems en Detalle (tipo 32, monto < DOP$250,000) | 10,000 |
| Formas de Pago (`<TablaFormasPago>`) | 7 |
| Subtotales (`<Subtotal>`) | 20 |
| Descuentos o Recargos (`<DescuentoORecargo>`) | 20 |
| Subdescuentos por ítem (`<TablaSubDescuento>`) | 12 |
| Subrecargos por ítem (`<TablaSubRecargo>`) | 12 |
| Impuestos Adicionales (`<ImpuestosAdicionales>`) | 20 |
| Códigos de Ítem (`<TablaCodigosItem>`) | 5 |
| Subcantidad (`<TablaSubcantidad>`) | 5 |

---

## 9. Firma Digital

### 9.1 Cobertura — la firma debe cubrir exactamente:

1. `<Encabezado>`
2. `<DetallesItem>`
3. `<DescuentosORecargos>`
4. `<Paginacion>`
5. `<InformacionReferencia>`
6. `<FechaHoraFirma>`

### 9.2 Exclusión

El tag `<Signature>` NO debe incluirse en el cálculo de la firma.

---

## 10. Formas de Pago

| Código | Forma de Pago |
|:---:|:---|
| 1 | Efectivo |
| 2 | Cheque / Transferencia / Depósito |
| 3 | Tarjeta de Débito/Crédito |
| 4 | Venta a Crédito |
| 5 | Bonos o Certificados de regalo (solo tipo 32) |
| 6 | Permuta |
| 7 | Nota de crédito |
| 8 | Otras formas de pago |

---

## 11. Tipos de Pago

| Código | Tipo |
|:---:|:---|
| 1 | Contado |
| 2 | Crédito |
| 3 | Gratuito (no válido para crédito fiscal) |

---

## 12. Tipos de Ingresos

| Código | Tipo de Ingreso |
|:---:|:---|
| 01 | Ingresos por operaciones (No financieros) |
| 02 | Ingresos Financieros |
| 03 | Ingresos Extraordinarios |
| 04 | Ingresos por Arrendamientos |
| 05 | Ingresos por Venta de Activo Depreciable |
| 06 | Otros Ingresos |

---

## 13. Tipos de Cuenta de Pago

| Código | Tipo |
|:---:|:---|
| CT | Cuenta Corriente |
| AH | Ahorro |
| OT | Otra |

---

## 14. Vía de Transporte

| Código | Vía |
|:---:|:---|
| 01 | Terrestre |
| 02 | Marítimo |
| 03 | Aérea |

---

## 15. Códigos de Modificación (Notas de Crédito/Débito)

| Código | Significado |
|:---:|:---|
| 1 | Anula el NCF modificado |
| 2 | Corrige texto del comprobante |
| 3 | Corrige montos del NCF modificado |
| 4 | Reemplaza NCF emitido en contingencia |
| 5 | Referencia Factura Consumo Electrónica |

---

## 16. Reglas para Descuentos o Recargos Globales

| Condición | Requisito |
|:---|:---|
| Descuentos/recargos que afectan el total | Incluir sección `<DescuentosORecargos>` |
| Ítems con distintos códigos de impuesto | Tipo de valor debe ser "%" |
| Descuento solo en ítems exentos | `IndicadorFacturacionDescuentoRecargo = 4` |
| Descuento solo en ítems gravados | `IndicadorFacturacionDescuentoRecargo = 1, 2 o 3` |
| Descuento en todos los ítems | Una línea por cada indicador presente |

Campos obligatorios del descuento/recargo:

| Campo | Tag XML | Valores |
|:---|:---|:---|
| Tipo de Ajuste | `<TipoAjuste>` | D (Descuento) o R (Recargo) |
| Tipo de valor | `<TipoValor>` | % o $ |
| Descripción | `<DescripcionDescuentooRecargo>` | Texto explicativo |

---

## 17. Validaciones de Formato

| Dato | Formato | Ejemplo |
|:---|:---|:---|
| Fecha | dd-MM-AAAA | 25-12-2025 |
| Hora (firma) | HH:mm:ss | 14:30:00 |
| Zona horaria | GMT -4 | Fijo |
| Decimales | Punto como separador | 1234.56 |
| Miles | Sin separadores | 1000000 |

---

## 18. Validaciones de Negocio

| Campo | Validación |
|:---|:---|
| `<RNCEmisor>` | Debe existir en DGII, estar activo, ser facturador electrónico, sin bloqueos |
| `<eNCF>` | Debe coincidir con secuencia autorizada por DGII |
| `<FechaVencimientoSecuencia>` | No debe haber expirado |
| `<RNCComprador>` | Obligatorio en tipo 32 con monto ≥ DOP$250,000 |
| `<MontoTotal>` en Nota Crédito | ≤ MontoTotal del e-CF modificado |

---

## 19. Representación Impresa (RI)

| Código | Significado |
|:---:|:---|
| I | Impresión OBLIGATORIA |
| P | Debe imprimirse EN PALABRAS |
| N | Impresión no obligatoria |

Ejemplos de campos que se imprimen en palabras: Tipo e-CF ("Factura Crédito Fiscal Electrónica", no "31"), Unidad de Medida ("Kilogramo", no "21"), Indicador de Facturación cuando es Exento ("E").

---

## 20. Tabla de Impuestos Adicionales

### 20.1 Impuestos porcentuales

| Código | Descripción | Tasa |
|:---:|:---|:---:|
| 001 | Propina Legal | 10% |
| 002 | CDT — Desarrollo Telecomunicaciones | 2% |
| 003 | ISC Servicios Seguros | 16% |
| 004 | Servicios de Telecomunicaciones | 10% |
| 005 | Impuesto Primer Registro Vehículos | 17% |

### 20.2 ISC Específico — Bebidas alcohólicas (006–018): RD$ 632.58 por unidad

Aplica a: cerveza, vinos, vermut, bebidas fermentadas, alcohol etílico (≥80% y <80%), aguardientes de uva, whisky, ron, gin, vodka, licores y demás bebidas/alcoholes.

### 20.3 ISC Específico — Cigarrillos

| Código | Descripción | Tasa (RD$) |
|:---:|:---|:---:|
| 019 | Cigarrillos con tabaco — cajetilla 20 und. | 53.51 |
| 020 | Los demás cigarrillos — 20 und. | 53.51 |
| 021 | Cigarrillos — 10 und. | 26.75 |
| 022 | Los demás cigarrillos — 10 und. | 26.75 |

### 20.4 ISC Ad Valorem — Bebidas alcohólicas (023–035): 10%

Aplica a los mismos productos que los códigos 006–018.

### 20.5 ISC Ad Valorem — Cigarrillos (036–039): 20%

Aplica a los mismos productos que los códigos 019–022.

> **Nota:** Para códigos 006–022, validar que la tasa esté vigente en la fecha de emisión (se ajusta trimestralmente por inflación).

---

## 21. Tabla de Monedas (ISO)

BRL, CAD, CHF, CHY, XDR, DKK, EUR, GBP, JPY, NOK, SCP, SEK, USD, VEF, HTG, MXN, COP.

> XDR (Derecho Especial de Giro) es unidad de cuenta del FMI, no una moneda.

---

## 22. Tabla de Unidades de Medida (62 unidades)

| Código | Abrev. | Medida |
|:---:|:---:|:---|
| 1 | BARR | Barril |
| 2 | BOL | Bolsa |
| 3 | BOT | Bote |
| 4 | BULTO | Bultos |
| 5 | BOTELLA | Botella |
| 6 | CAJ | Caja/Cajón |
| 7 | CAJETILLA | Cajetilla |
| 8 | CM | Centímetro |
| 9 | CIL | Cilindro |
| 10 | CONJ | Conjunto |
| 11 | CONT | Contenedor |
| 12 | DÍA | Día |
| 13 | DOC | Docena |
| 14 | FARD | Fardo |
| 15 | GL | Galones |
| 16 | GRAD | Grado |
| 17 | GR | Gramo |
| 18 | GRAN | Granel |
| 19 | HOR | Hora |
| 20 | HUAC | Huacal |
| 21 | KG | Kilogramo |
| 22 | kWh | Kilovatio Hora |
| 23 | LB | Libra |
| 24 | LITRO | Litro |
| 25 | LOT | Lote |
| 26 | M | Metro |
| 27 | M2 | Metro Cuadrado |
| 28 | M3 | Metro Cúbico |
| 29 | MMBTU | Millones de Unidades Térmicas |
| 30 | MIN | Minuto |
| 31 | PAQ | Paquete |
| 32 | PAR | Par |
| 33 | PIE | Pie |
| 34 | PZA | Pieza |
| 35 | ROL | Rollo |
| 36 | SOBR | Sobre |
| 37 | SEG | Segundo |
| 38 | TANQUE | Tanque |
| 39 | TON | Tonelada |
| 40 | TUB | Tubo |
| 41 | YD | Yarda |
| 42 | YD² | Yarda cuadrada |
| 43 | UND | Unidad |
| 44 | EA | Elemento |
| 45 | MILLAR | Millar |
| 46 | SAC | Saco |
| 47 | LAT | Lata |
| 48 | DIS | Display |
| 49 | BID | Bidón |
| 50 | RAC | Ración |
| 51 | Q | Quintal |
| 52 | GRT | Gross Register Tonnage |
| 53 | P2 | Pie cuadrado |
| 54 | PAX | Pasajero |
| 55 | PULG | Pulgadas |
| 56 | STAY | Parqueo barcos en muelle |
| 57 | BDJ | Bandeja |
| 58 | HA | Hectárea |
| 59 | ML | Mililitro |
| 60 | MG | Miligramo |
| 61 | OZ | Onzas |
| 62 | OZT | Onzas Troy |

> Unidad de medida "Granel" (código 18): no aplica ISC Específico. Para ISC Ad Valorem con Granel, incrementar precio unitario en 30%.

---

## 23. Tabla de Provincias y Municipios

Código Provincia: 6 dígitos (ej: `010000` = Distrito Nacional). Código Municipio: 6 dígitos (ej: `010100` = Santo Domingo de Guzmán).

| Código | Provincia |
|:---:|:---|
| 010000 | Distrito Nacional |
| 020000 | Azua |
| 030000 | Bahoruco |
| 040000 | Barahona |
| 050000 | Dajabón |
| 060000 | Duarte |
| 070000 | Elías Piña |
| 080000 | El Seibo |
| 090000 | Espaillat |
| 100000 | Independencia |
| 110000 | La Altagracia |
| 120000 | La Romana |
| 130000 | La Vega |
| 140000 | María Trinidad Sánchez |
| 150000 | Monte Cristi |
| 160000 | Pedernales |
| 170000 | Peravia |
| 180000 | Puerto Plata |
| 190000 | Hermanas Mirabal |
| 200000 | Samaná |
| 210000 | San Cristóbal |
| 220000 | San Juan |
| 230000 | San Pedro de Macorís |
| 240000 | Sánchez Ramírez |
| 250000 | Santiago |
| 260000 | Santiago Rodríguez |
| 270000 | Valverde |
| 280000 | Monseñor Nouel |
| 290000 | Monte Plata |
| 300000 | Hato Mayor |
| 310000 | San José de Ocoa |
| 320000 | Santo Domingo |

> Fuente: ONE, actualizada al 30 de junio de 2014.

---

## 24. Bitácora de Cambios (Versión 1.0)

| Fecha | Cambio |
|:---|:---|
| 09-10-2025 | Agregar Peso Colombiano (COP) a Tabla de Monedas |
| 17-09-2024 | Agregar Gurda Haitiana (HTG) y Peso Mexicano (MXN) |
| 17-09-2024 | Agregar Hectárea, Mililitro, Miligramo, Onzas, Onzas Troy a Unidades |
| 30-08-2022 | Agregar Bandeja a Unidades |
| 06-05-2022 | Agregar GRT, Pie cuadrado, Pasajero, Pulgadas, Parqueo Barcos |
| 19-11-2021 | Códigos de obligatoriedad en área Comprador para Nota Crédito/Débito |
| 04-11-2021 | Agregar Quintal a Unidades |
| 29-06-2021 | Separar columnas de códigos de Provincias y Municipios |
| 28-07-2020 | Permitir valor 0 en `TotalITBISRetenido` y `TotalISRRetencion` |

---

*Basado en: Formato Comprobante Fiscal Electrónico (e-CF) Versión 1.0 | Octubre 2025 — DGII República Dominicana*