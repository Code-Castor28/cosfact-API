from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers
from django.core.exceptions import ValidationError

from .models import Comprobante, ComprobanteDetalle


class ComprobanteDetalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComprobanteDetalle
        fields = [
            "numero_linea", "indicador_facturacion", "nombre_item",
            "cantidad", "unidad_medida", "precio_unitario_item",
            "descuento_monto", "monto_item",
        ]

    def validate(self, attrs):
        if attrs.get("indicador_facturacion") == 0:
            raise serializers.ValidationError(
                "El Indicador de Facturación '0' (No Facturable) "
                "no está soportado en esta versión corporativa."
            )

        calculado = (
            (attrs["cantidad"] * attrs["precio_unitario_item"])
            - attrs.get("descuento_monto", 0)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if calculado != attrs["monto_item"]:
            raise serializers.ValidationError(
                {"monto_item": f"Valor incorrecto. Esperado: {calculado}"}
            )
        return attrs


class ComprobanteCreateSerializer(serializers.ModelSerializer):
    detalles = ComprobanteDetalleSerializer(many=True, write_only=True)
    emitir_inmediatamente = serializers.BooleanField(default=True, write_only=True)

    class Meta:
        model = Comprobante
        fields = "__all__"
        read_only_fields = [
            "id", "encf", "estado", "estado_dgii", "celery_task_id",
            "creado_at", "actualizado_at",
            "codigo_seguridad_dgii", "xml_path",
            "valor_pagar", "track_id_dgii", "idempotency_key",
        ]

    def validate(self, attrs):
        detalles = attrs.get("detalles", [])
        tipo = attrs.get("tipo_ecf")
        monto = attrs.get("monto_total", Decimal("0"))
        max_lineas = self._limite_lineas_por_tipo(tipo, monto)
        if len(detalles) > max_lineas:
            raise serializers.ValidationError({
                "detalles": (
                    f"Tipo e-CF {tipo} permite máximo {max_lineas} líneas. "
                    f"Recibidas: {len(detalles)}."
                )
            })

        self._validar_tipo(attrs)
        self._validar_comprador(attrs)
        self._validar_nota_modificacion(attrs)
        self._validar_totales(attrs)
        return attrs

    def _limite_lineas_por_tipo(self, tipo, monto):
        if tipo == 32:
            if monto >= Decimal("250000.00"):
                return 1000
            return 10000
        return 100

    def _validar_totales(self, attrs):
        TASAS = {1: Decimal("0.18"), 2: Decimal("0.16"), 3: Decimal("0.00")}
        monto_gravado = Decimal("0")
        monto_exento = Decimal("0")
        total_itbis = Decimal("0")
        monto_impuesto_adicional = attrs.get("monto_impuesto_adicional", Decimal("0"))

        for item in attrs.get("detalles", []):
            monto = item["monto_item"]
            indicador = item["indicador_facturacion"]
            if indicador in TASAS:
                tasa = TASAS[indicador]
                if attrs.get("indicador_monto_gravado") == 1:
                    base = (monto / (1 + tasa)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                else:
                    base = monto
                itbis = (base * tasa).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                monto_gravado += base
                total_itbis += itbis
            elif indicador == 4:
                monto_exento += monto

        total_calculado = (
            monto_gravado + monto_exento + total_itbis + monto_impuesto_adicional
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total_calculado != attrs["monto_total"]:
            raise serializers.ValidationError({
                "monto_total": (
                    f"Sumatoria calculada ({total_calculado}) no coincide "
                    f"con monto_total declarado ({attrs['monto_total']})."
                )
            })

    def _validar_comprador(self, attrs):
        tipo = attrs.get("tipo_ecf")
        if tipo == 31:
            if not attrs.get("rnc_comprador") or not attrs.get("razon_social_comprador"):
                raise serializers.ValidationError(
                    "Tipo 31 requiere rnc_comprador y razon_social_comprador."
                )
        if tipo == 32:
            monto = attrs.get("monto_total", Decimal("0"))
            if monto >= Decimal("250000.00"):
                if not attrs.get("rnc_comprador") and not attrs.get("cedula_comprador"):
                    raise serializers.ValidationError(
                        "Tipo 32 con monto >= RD$250,000 requiere "
                        "rnc_comprador o cedula_comprador."
                    )
            else:
                if not attrs.get("rnc_comprador"):
                    attrs["razon_social_comprador"] = "CONSUMIDOR FINAL"

    def _validar_nota_modificacion(self, attrs):
        if attrs.get("tipo_ecf") in [33, 34]:
            ncf_mod = attrs.get("ncf_modificado")
            if not ncf_mod:
                raise serializers.ValidationError(
                    "Tipos 33/34 requieren ncf_modificado."
                )

    def _validar_tipo(self, attrs):
        TIPOS_PERMITIDOS = [31, 32, 33, 34, 41]
        if attrs.get("tipo_ecf") not in TIPOS_PERMITIDOS:
            raise serializers.ValidationError(
                f"Tipo de e-CF no permitido en esta fase. "
                f"Permitidos: {TIPOS_PERMITIDOS}"
            )
