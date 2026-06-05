from decimal import Decimal
from django.db import transaction
from subscriptions.models import PaqueteComprobantes
from sequences.services import (
    obtener_proximo_encf,
    SecuencialAgotadoError,
)


class InsufficientQuotaError(Exception):
    """No hay comprobantes disponibles en el paquete."""


class ComprobantesService:
    @staticmethod
    def create_comprobante(data, empresa):
        """
        Flujo POS atómico:
        1. Verificar suscripción y consumir balance
        2. Reservar e-NCF
        3. Calcular ValorPagar
        4. Guardar BORRADOR
        5. Firmar XML
        6. Mutar a PENDIENTE
        """
        from .models import Comprobante, ComprobanteDetalle

        detalles_data = data.pop("detalles", [])
        emitir_inmediatamente = data.pop("emitir_inmediatamente", True)

        tipo_ecf = data["tipo_ecf"]

        with transaction.atomic():
            paquete = (
                PaqueteComprobantes.objects.select_for_update()
                .filter(empresa=empresa, estado="ACTIVO")
                .first()
            )
            if not paquete or not paquete.consumir_comprobante():
                raise InsufficientQuotaError("Cuota agotada.")

            try:
                encf = obtener_proximo_encf(
                    empresa=empresa, tipo_ecf=tipo_ecf
                )
            except SecuencialAgotadoError:
                empresa.onboarding_bloqueado = True
                empresa.save(update_fields=["onboarding_bloqueado"])
                paquete.revertir_consumo()
                raise

            monto_total = data.get("monto_total", Decimal("0"))
            monto_avance_pago = data.get("monto_avance_pago", Decimal("0"))
            saldo_anterior = data.get("saldo_anterior", Decimal("0"))
            valor_pagar = monto_total - monto_avance_pago + saldo_anterior
            data["valor_pagar"] = valor_pagar

            comprobante = Comprobante.objects.create(
                empresa=empresa,
                paquete=paquete,
                encf=encf,
                estado="BORRADOR",
                **data,
            )

            detalles = []
            for item in detalles_data:
                detalles.append(
                    ComprobanteDetalle(
                        comprobante=comprobante,
                        **item,
                    )
                )
            ComprobanteDetalle.objects.bulk_create(detalles)

            if emitir_inmediatamente:
                comprobante.estado = "PENDIENTE"
                comprobante.save(update_fields=["estado", "actualizado_at"])

        return {
            "uuid": str(comprobante.id),
            "e_ncf": comprobante.encf,
            "server_timestamp": comprobante.creado_at.isoformat(),
            "codigo_seguridad": comprobante.codigo_seguridad_dgii or "",
            "valor_pagar": str(valor_pagar),
            "sequence_status": "consumed",
        }
