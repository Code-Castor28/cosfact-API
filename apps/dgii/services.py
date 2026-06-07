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


def _get_certificado_activo(empresa: Empresa):
    """
    Obtiene el certificado activo de la empresa desde CertificadoDigital.
    """
    from empresas.models import CertificadoDigital

    cert = CertificadoDigital.objects.filter(
        empresa=empresa, activo=True
    ).first()
    if not cert:
        raise ValueError(
            f"No hay certificado activo para empresa {empresa.rnc}"
        )
    if not cert.archivo:
        raise ValueError(
            f"El certificado activo de {empresa.rnc} no tiene archivo .p12"
        )
    if not cert.pin_cifrado:
        raise ValueError(
            f"El certificado activo de {empresa.rnc} no tiene PIN configurado"
        )
    return cert


def _cert_path_for_empresa(empresa: Empresa) -> str:
    """
    Obtiene la ruta del archivo .p12 desde CertificadoDigital.
    """
    cert = _get_certificado_activo(empresa)
    return cert.archivo.path


def _get_cert_pin(empresa: Empresa) -> str:
    """
    Obtiene el PIN del certificado descifrándolo desde CertificadoDigital.
    El PIN se descifra en memoria con Fernet y se descarta tras usarlo.
    """
    from empresas.crypto import descifrar

    cert = _get_certificado_activo(empresa)
    return descifrar(cert.pin_cifrado)


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


def _ejecutar_envio(comprobante: Comprobante) -> tuple[dict, int]:
    """
    Lógica pura de XML + firma + envío HTTP a DGII.
    No toca estados ni transacciones.
    Retorna (respuesta_dict, duracion_ms).
    """
    detalles = list(comprobante.detalles.all())
    xml_bytes = build_ecf_xml(comprobante, detalles)
    cert_path = _cert_path_for_empresa(comprobante.empresa)
    cert_pin = _get_cert_pin(comprobante.empresa)
    xml_firmado = sign_xml(xml_bytes, cert_path, cert_pin)

    xml_path = _xml_path_for_comprobante(comprobante)
    xml_hash = _save_xml(xml_firmado, xml_path)

    with transaction.atomic():
        c = Comprobante.objects.select_for_update().get(pk=comprobante.id)
        c.xml_path = xml_path
        c.xml_hash = xml_hash
        c.xml_version = "1.0"
        c.save(update_fields=["xml_path", "xml_hash", "xml_version", "actualizado_at"])

    client = DgiiClient(comprobante.empresa)
    respuesta = client.enviar_ecf(xml_firmado)
    return respuesta, client.timeout


def emitir_ecf(comprobante_id: str, forzar_reintento=False) -> Comprobante:
    """
    Emite un e-CF contra DGII.
    Maneja estado y estado_dgii según la tabla de decisión.
    """
    with transaction.atomic():
        comprobante = (
            Comprobante.objects
            .select_for_update()
            .select_related("empresa")
            .get(pk=comprobante_id)
        )

        if comprobante.estado_dgii == Comprobante.ESTADO_DGII_ACEPTADO:
            return comprobante

        if comprobante.estado_dgii == Comprobante.ESTADO_DGII_RECHAZADO and not forzar_reintento:
            return comprobante

        estado_anterior = comprobante.estado
        estado_dgii_anterior = comprobante.estado_dgii

        if not comprobante.encf:
            comprobante.encf = obtener_proximo_encf(
                comprobante.empresa,
                comprobante.tipo_ecf,
                comprobante=comprobante,
            )

        comprobante.estado = Comprobante.ESTADO_EMITIDO
        comprobante.estado_dgii = Comprobante.ESTADO_DGII_ENVIADO
        comprobante.save(update_fields=["encf", "estado", "estado_dgii", "actualizado_at"])

        _crear_evento(comprobante, estado_anterior,
                      comprobante.estado, "Inicio de envio DGII")

    try:
        respuesta, _timeout = _ejecutar_envio(comprobante)
    except DgiiClientError as exc:
        es_timeout = "timeout" in str(exc).lower() or "timed out" in str(exc).lower()
        if es_timeout:
            _marcar_contingencia(comprobante_id, str(exc))
        else:
            _marcar_error_red(comprobante_id, str(exc))
        raise

    track_id = respuesta.get("track_id") or ""
    estado_dgii_final_str = respuesta.get("estado") or ""

    with transaction.atomic():
        comprobante = Comprobante.objects.select_for_update().get(pk=comprobante_id)
        estado_dgii_anterior = comprobante.estado_dgii

        comprobante.track_id_dgii = track_id
        comprobante.intentos_envio = comprobante.intentos_envio + 1
        comprobante.ultimo_error = ""

        if estado_dgii_final_str == "ACEPTADO":
            comprobante.estado_dgii = Comprobante.ESTADO_DGII_ACEPTADO
        elif estado_dgii_final_str == "RECHAZADO":
            comprobante.estado_dgii = Comprobante.ESTADO_DGII_RECHAZADO

        comprobante.save(update_fields=[
            "track_id_dgii", "estado_dgii",
            "intentos_envio", "ultimo_error", "actualizado_at",
        ])

        _crear_evento(comprobante, estado_dgii_anterior,
                      comprobante.estado_dgii, "Envio DGII completado")

        _crear_dgiilog_envio(comprobante, track_id, estado_dgii_final_str)

    from webhooks.services import disparar_webhook
    if comprobante.estado_dgii in (
        Comprobante.ESTADO_DGII_ACEPTADO,
        Comprobante.ESTADO_DGII_RECHAZADO,
    ):
        disparar_webhook(
            comprobante.empresa,
            f"comprobante.{comprobante.estado_dgii.lower()}",
            {
                "comprobante_id": str(comprobante.id),
                "encf": comprobante.encf,
                "estado": comprobante.estado_dgii,
                "rnc": comprobante.empresa.rnc,
                "fecha_emision": comprobante.fecha_emision.isoformat(),
            },
        )

    return comprobante


def _crear_dgiilog_envio(comprobante, track_id, estado_final):
    from dgii.models import DGIILog
    DGIILog.objects.create(
        empresa=comprobante.empresa,
        comprobante=comprobante,
        ambiente=comprobante.empresa.ambiente or "",
        tipo_operacion="ENVIO_ECF",
        endpoint="/Recepcion/api/FacturasElectronicas",
        estado_respuesta=estado_final or "",
        codigo_dgii=track_id[:50],
        exitoso=estado_final == "ACEPTADO",
    )


def _marcar_contingencia(comprobante_id: str, error: str):
    with transaction.atomic():
        comprobante = Comprobante.objects.select_for_update().get(pk=comprobante_id)
        estado_anterior = comprobante.estado
        estado_dgii_anterior = comprobante.estado_dgii
        comprobante.estado = Comprobante.ESTADO_CONTINGENCIA
        comprobante.estado_dgii = Comprobante.ESTADO_DGII_CONTINGENCIA
        comprobante.intentos_envio = comprobante.intentos_envio + 1
        comprobante.ultimo_error = error[:2000]
        comprobante.save(update_fields=[
            "estado", "estado_dgii", "intentos_envio", "ultimo_error", "actualizado_at",
        ])
        _crear_evento(comprobante, estado_anterior,
                      comprobante.estado, "Contingencia DGII")


def _marcar_error_red(comprobante_id: str, error: str):
    with transaction.atomic():
        comprobante = Comprobante.objects.select_for_update().get(pk=comprobante_id)
        estado_dgii_anterior = comprobante.estado_dgii
        comprobante.estado_dgii = Comprobante.ESTADO_DGII_ERROR_RED
        comprobante.intentos_envio = comprobante.intentos_envio + 1
        comprobante.ultimo_error = error[:2000]
        comprobante.save(update_fields=[
            "estado_dgii", "intentos_envio", "ultimo_error", "actualizado_at",
        ])
        _crear_evento(comprobante, estado_dgii_anterior,
                      comprobante.estado_dgii, "Error de red DGII")


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
        estado_dgii_anterior = comprobante.estado_dgii
        comprobante.estado_dgii = estado
        comprobante.save(update_fields=["estado_dgii", "actualizado_at"])
        _crear_evento(comprobante, estado_dgii_anterior,
                      comprobante.estado_dgii, "Consulta estado DGII")

    from dgii.models import DGIILog
    DGIILog.objects.create(
        empresa=comprobante.empresa,
        comprobante=comprobante,
        ambiente=comprobante.empresa.ambiente or "",
        tipo_operacion="CONSULTA_ESTADO",
        estado_respuesta=estado,
        exitoso=estado == "ACEPTADO",
    )

    from webhooks.services import disparar_webhook
    if estado in (
        "ACEPTADO",
        "RECHAZADO",
    ):
        disparar_webhook(
            comprobante.empresa,
            f"comprobante.{estado.lower()}",
            {
                "comprobante_id": str(comprobante.id),
                "encf": comprobante.encf,
                "estado": estado,
                "rnc": comprobante.empresa.rnc,
                "fecha_emision": comprobante.fecha_emision.isoformat(),
            },
        )

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
