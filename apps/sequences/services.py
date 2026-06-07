# ─── SERVICES.PY — apps/sequences/services.py ───
"""
apps/sequences/services.py

Servicio para obtener el próximo e-NCF de forma atómica.

DISEÑO DE SEGURIDAD:
- La única forma de obtener un número es a través de obtener_proximo_encf().
- El SELECT FOR UPDATE está en este servicio — es el único punto de entrada.
- Nunca llamar secuencial.save() directamente desde fuera de este servicio
  para modificar ultimo_numero.
"""
from django.db import transaction
from django.utils import timezone
from .models import Secuencial, MovimientoSecuencial, TIPOS_ECF


class SecuencialAgotadoError(Exception):
    """El rango de secuenciales se ha agotado."""


class TipoECFBloqueadoError(Exception):
    """El tipo de e-CF está bloqueado temporalmente."""


class TipoECFNoExisteError(Exception):
    """No hay secuencial configurado para este tipo en esta empresa."""


def obtener_proximo_encf(empresa, tipo_ecf: int, comprobante=None, usuario=None) -> str:
    """
    Obtiene y reserva el próximo número e-NCF para la empresa y tipo dado.

    ATÓMICO: Usa SELECT FOR UPDATE para evitar que dos workers obtengan
    el mismo número. Llama siempre dentro de un contexto de transacción
    más amplio (el de la emisión del comprobante).

    Args:
        empresa: instancia de Empresa
        tipo_ecf: int, tipo de comprobante (31, 32, 41, etc.)
        comprobante: opcional, instancia de Comprobante para auditoría
        usuario: opcional, instancia de Usuario para auditoría

    Returns:
        str: el e-NCF formateado, ej: "E310000001"

    Raises:
        TipoECFNoExisteError: si no hay secuencial configurado
        TipoECFBloqueadoError: si el tipo está bloqueado
        SecuencialAgotadoError: si se agotó el rango
    """
    if tipo_ecf not in TIPOS_ECF:
        raise ValueError(f"Tipo e-CF inválido: {tipo_ecf}")

    try:
        with transaction.atomic():
            try:
                secuencial = Secuencial.objects.select_for_update().get(
                    empresa=empresa,
                    tipo_ecf=tipo_ecf,
                )
            except Secuencial.DoesNotExist:
                raise TipoECFNoExisteError(
                    f"No hay secuencial configurado para tipo {tipo_ecf} "
                    f"en la empresa {empresa.rnc}."
                )

            if secuencial.bloqueado:
                raise TipoECFBloqueadoError(
                    f"El tipo {tipo_ecf} está bloqueado. "
                    f"Motivo: {secuencial.motivo_bloqueo or 'Sin especificar'}"
                )

            proximo = secuencial.ultimo_numero + 1

            if proximo > secuencial.maximo_asignado:
                raise SecuencialAgotadoError(
                    f"El rango de secuenciales para tipo {tipo_ecf} se ha agotado. "
                    f"Máximo: {secuencial.maximo_asignado}."
                )

            secuencial.ultimo_numero = proximo
            secuencial.save(update_fields=["ultimo_numero", "actualizado_at"])

            encf = secuencial._formatear_encf(proximo)

            MovimientoSecuencial.objects.create(
                secuencial=secuencial,
                empresa=empresa,
                tipo_ecf=tipo_ecf,
                numero_asignado=proximo,
                encf_generado=encf,
                comprobante=comprobante,
                usuario=usuario,
            )

            return encf
    except SecuencialAgotadoError:
        with transaction.atomic():
            Secuencial.objects.filter(
                empresa=empresa, tipo_ecf=tipo_ecf,
            ).update(
                bloqueado=True,
                motivo_bloqueo="Rango agotado automáticamente.",
                fecha_bloqueo=timezone.now(),
            )
        raise
