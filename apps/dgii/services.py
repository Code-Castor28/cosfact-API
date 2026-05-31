# ─── SERVICES.PY — apps/dgii/services.py ───
"""
Servicios de integracion con DGII y manejo de contingencia.
"""
from datetime import datetime, timezone

from django.conf import settings
from django.db import transaction

from comprobantes.models import Comprobante, ComprobanteEvento
from empresas.models import Empresa
from sequences.services import obtener_proximo_encf

from dgii.utils.dgii_client import DgiiClient, DgiiClientError
from dgii.utils.xml_builder import build_ecf_xml
from dgii.utils.xml_signer import sign_xml


def _crear_evento(comprobante, estado_anterior, estado_nuevo, mensaje=""):
    ComprobanteEvento.objects.create(
        comprobante=comprobante,
        estado_anterior=estado_anterior or "",
        estado_nuevo=estado_nuevo,
        mensaje=mensaje or "",
    )


def _cert_path_for_empresa(empresa: Empresa) -> str:
    base = getattr(settings, "CERT_BASE_PATH", None) or ""
    if not base:
        base = "/var/derejfact/certificados/"
    return f"{base.rstrip('/')}/{empresa.id}.p12"


def _get_cert_pin(empresa: Empresa) -> str:
    from os import environ

    env_key = f"CERT_PIN_{empresa.id}"
    pin = environ.get(env_key)
    if not pin:
        raise ValueError(f"No existe {env_key} en variables de entorno.")
    return pin


def _xml_path_for_comprobante(comprobante: Comprobante) -> str:
    base = getattr(settings, "XML_BASE_PATH", None) or ""
    if not base:
        base = "/var/derejfact/xmls/"
    year = comprobante.fecha_emision.year
    nombre = comprobante.encf or f"{comprobante.id}"
    return f"{base.rstrip('/')}/{comprobante.empresa_id}/ecf/{year}/{nombre}.xml"


def _save_xml(xml_bytes: bytes, path: str) -> str:
    import hashlib
    import os

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(xml_bytes)
    return hashlib.sha256(xml_bytes).hexdigest()


def emitir_ecf(comprobante_id: str, forzar_reintento=False) -> Comprobante:
    """
    Emite un e-CF: construye XML, firma, envia a DGII y actualiza estado.
    Si hay fallo tecnico, pone CONTINGENCIA y lanza excepcion para reintento.
    """
    with transaction.atomic():
        comprobante = (
            Comprobante.objects
            .select_for_update()
            .select_related("empresa")
            .get(pk=comprobante_id)
        )

        if comprobante.estado in (Comprobante.ESTADO_ACEPTADO, Comprobante.ESTADO_ANULADO):
            return comprobante

        if comprobante.estado == Comprobante.ESTADO_RECHAZADO and not forzar_reintento:
            return comprobante

        estado_anterior = comprobante.estado

        if not comprobante.encf:
            comprobante.encf = obtener_proximo_encf(
                comprobante.empresa,
                comprobante.tipo_ecf,
                comprobante=comprobante,
            )

        comprobante.estado = Comprobante.ESTADO_PROCESANDO
        comprobante.save(update_fields=["encf", "estado", "actualizado_at"])

        _crear_evento(comprobante, estado_anterior,
                      comprobante.estado, "Inicio de envio DGII")

    xml_bytes = build_ecf_xml(comprobante, list(comprobante.detalles.all()))
    cert_path = _cert_path_for_empresa(comprobante.empresa)
    cert_pin = _get_cert_pin(comprobante.empresa)
    xml_firmado = sign_xml(xml_bytes, cert_path, cert_pin)

    xml_path = _xml_path_for_comprobante(comprobante)
    xml_hash = _save_xml(xml_firmado, xml_path)

    with transaction.atomic():
        comprobante = Comprobante.objects.select_for_update().get(pk=comprobante_id)
        comprobante.xml_path = xml_path
        comprobante.xml_hash = xml_hash
        comprobante.xml_version = "1.0"
        comprobante.save(
            update_fields=["xml_path", "xml_hash", "xml_version", "actualizado_at"])

    client = DgiiClient(comprobante.empresa)
    try:
        respuesta = client.enviar_ecf(xml_firmado)
    except DgiiClientError as exc:
        _marcar_contingencia(comprobante_id, str(exc))
        raise

    track_id = respuesta.get("track_id") or ""
    estado_final = respuesta.get("estado") or Comprobante.ESTADO_PROCESANDO

    with transaction.atomic():
        comprobante = Comprobante.objects.select_for_update().get(pk=comprobante_id)
        estado_anterior = comprobante.estado
        comprobante.track_id_dgii = track_id
        comprobante.estado = estado_final
        comprobante.intentos_envio = comprobante.intentos_envio + 1
        comprobante.ultimo_error = ""
        comprobante.save(update_fields=[
            "track_id_dgii",
            "estado",
            "intentos_envio",
            "ultimo_error",
            "actualizado_at",
        ])
        _crear_evento(comprobante, estado_anterior,
                      comprobante.estado, "Envio DGII completado")

    return comprobante


def _marcar_contingencia(comprobante_id: str, error: str):
    with transaction.atomic():
        comprobante = Comprobante.objects.select_for_update().get(pk=comprobante_id)
        estado_anterior = comprobante.estado
        comprobante.estado = Comprobante.ESTADO_CONTINGENCIA
        comprobante.intentos_envio = comprobante.intentos_envio + 1
        comprobante.ultimo_error = error[:2000]
        comprobante.save(
            update_fields=["estado", "intentos_envio", "ultimo_error", "actualizado_at"])
        _crear_evento(comprobante, estado_anterior,
                      comprobante.estado, "Contingencia DGII")


def marcar_error_tecnico(comprobante_id: str, error: str):
    with transaction.atomic():
        comprobante = Comprobante.objects.select_for_update().get(pk=comprobante_id)
        estado_anterior = comprobante.estado
        comprobante.estado = Comprobante.ESTADO_ERROR
        comprobante.intentos_envio = comprobante.intentos_envio + 1
        comprobante.ultimo_error = error[:2000]
        comprobante.save(
            update_fields=["estado", "intentos_envio", "ultimo_error", "actualizado_at"])
        _crear_evento(comprobante, estado_anterior,
                      comprobante.estado, "Error tecnico DGII")


def consultar_estado(comprobante_id: str) -> Comprobante:
    comprobante = Comprobante.objects.select_related(
        "empresa").get(pk=comprobante_id)
    if not comprobante.track_id_dgii:
        return comprobante

    client = DgiiClient(comprobante.empresa)
    respuesta = client.consultar_estado(comprobante.track_id_dgii)
    estado = respuesta.get("estado")
    if not estado:
        return comprobante

    with transaction.atomic():
        comprobante = Comprobante.objects.select_for_update().get(pk=comprobante_id)
        estado_anterior = comprobante.estado
        comprobante.estado = estado
        comprobante.save(update_fields=["estado", "actualizado_at"])
        _crear_evento(comprobante, estado_anterior,
                      comprobante.estado, "Consulta estado DGII")
    return comprobante


def _parse_jwt_exp(token: str):
    import jwt

    try:
        data = jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return None
    exp = data.get("exp")
    if not exp:
        return None
    return datetime.fromtimestamp(exp, tz=timezone.utc)
