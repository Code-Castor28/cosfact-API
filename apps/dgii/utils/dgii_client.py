# ─── DGII_CLIENT.PY — apps/dgii/utils/dgii_client.py ───
"""
Cliente DGII (autenticacion, envio, consulta, anulacion).
"""
from datetime import datetime, timedelta, timezone
import requests

from django.conf import settings

from empresas.models import TokenDGII
from empresas.crypto import cifrar, descifrar
from dgii.models import DGIILog


class DgiiClientError(Exception):
    pass


class DgiiClient:
    def __init__(self, empresa):
        self.empresa = empresa
        self.ambiente = empresa.ambiente
        self.base_url = self._base_url_for_ambiente(empresa.ambiente)
        self.timeout = getattr(settings, "DGII_TIMEOUT", 20)

    def _base_url_for_ambiente(self, ambiente: str) -> str:
        return f"https://ecf.dgii.gov.do/{ambiente}"

    def _log(self, tipo, endpoint, http_status=None, request_xml="", response_xml="", exitoso=False, mensaje="", duracion_ms=None):
        try:
            DGIILog.objects.create(
                empresa=self.empresa,
                ambiente=self.ambiente,
                tipo_operacion=tipo,
                endpoint=endpoint,
                http_status=http_status,
                request_xml_cifrado=cifrar(request_xml) if request_xml else "",
                response_xml_cifrado=cifrar(response_xml) if response_xml else "",
                exitoso=exitoso,
                mensaje=mensaje or "",
                duracion_ms=duracion_ms,
            )
        except Exception:
            pass

    def _request(self, method, endpoint, headers=None, data=None):
        url = f"{self.base_url}{endpoint}"
        start = datetime.now(tz=timezone.utc)
        try:
            response = requests.request(
                method,
                url,
                headers=headers or {},
                data=data,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            self._log("ENVIO_ECF", endpoint, mensaje=str(exc))
            raise DgiiClientError(str(exc))
        duracion_ms = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)
        return response, duracion_ms

    def _get_token(self) -> str:
        ahora = datetime.now(tz=timezone.utc)
        token = (
            TokenDGII.objects
            .filter(empresa=self.empresa, ambiente=self.ambiente, activo=True)
            .order_by("-expira_at")
            .first()
        )
        if token and token.expira_at > ahora + timedelta(minutes=1):
            return descifrar(token.token_cifrado)

        return self._autenticar()

    def _autenticar(self) -> str:
        semilla_endpoint = "/Autenticacion/api/Autenticacion/Semilla"
        response, duracion_ms = self._request("GET", semilla_endpoint)
        if response.status_code != 200:
            self._log("OBTENER_SEMILLA", semilla_endpoint, response.status_code, response.text, response.text, False, "Error semilla", duracion_ms)
            raise DgiiClientError("Error obteniendo semilla DGII")

        semilla_xml = response.text
        self._log("OBTENER_SEMILLA", semilla_endpoint, response.status_code, semilla_xml, response.text, True, "Semilla OK", duracion_ms)

        raise DgiiClientError("ValidarSemilla no implementado en dgii_client.py")

    def enviar_ecf(self, xml_firmado: bytes) -> dict:
        token = self._get_token()
        endpoint = "/Recepcion/api/FacturasElectronicas"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/xml",
        }
        response, duracion_ms = self._request("POST", endpoint, headers=headers, data=xml_firmado)
        exitoso = response.status_code == 200
        self._log("ENVIO_ECF", endpoint, response.status_code, xml_firmado.decode(errors="ignore"), response.text, exitoso, "", duracion_ms)

        if not exitoso:
            raise DgiiClientError(f"DGII envio e-CF fallo: {response.status_code}")

        return {
            "track_id": _extraer_track_id(response.text),
            "estado": None,
        }

    def consultar_estado(self, track_id: str) -> dict:
        token = self._get_token()
        endpoint = f"/Consultas/api/Consultas/Estado/{track_id}"
        headers = {"Authorization": f"Bearer {token}"}
        response, duracion_ms = self._request("GET", endpoint, headers=headers)
        exitoso = response.status_code == 200
        self._log("CONSULTA_ESTADO", endpoint, response.status_code, "", response.text, exitoso, "", duracion_ms)
        if not exitoso:
            raise DgiiClientError(f"DGII consulta estado fallo: {response.status_code}")
        return {
            "estado": _extraer_estado(response.text),
        }


def _extraer_track_id(xml_text: str) -> str:
    import re

    match = re.search(r"<TrackId>([^<]+)</TrackId>", xml_text)
    if match:
        return match.group(1)
    return ""


def _extraer_estado(xml_text: str) -> str:
    import re

    match = re.search(r"<Estado>([^<]+)</Estado>", xml_text)
    if match:
        return match.group(1)
    return ""
