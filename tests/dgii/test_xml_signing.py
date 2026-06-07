import base64
import contextlib
import os
import tempfile

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree

MINIMAL_ECF_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ECF xmlns="http://dgii.gov.do/ecf" Id="ECF">
  <Encabezado>
    <IdDoc>
      <TipoeCF>31</TipoeCF>
      <eNCF>E310000000001</eNCF>
      <FechaEmision>2026-06-07</FechaEmision>
    </IdDoc>
    <Emisor>
      <RNCEmisor>12345678901</RNCEmisor>
    </Emisor>
    <Comprador>
      <RNCComprador>99999999999</RNCComprador>
      <RazonSocialComprador>Comprador Test</RazonSocialComprador>
    </Comprador>
    <Totales>
      <MontoGravadoTotal>1000.00</MontoGravadoTotal>
      <MontoExento>0.00</MontoExento>
      <TotalITBIS18>180.00</TotalITBIS18>
      <MontoTotal>1180.00</MontoTotal>
    </Totales>
  </Encabezado>
  <DetalleItems>
    <Item>
      <NumeroLinea>1</NumeroLinea>
      <NombreItem>Producto de prueba</NombreItem>
      <CantidadItem>1</CantidadItem>
      <PrecioUnitarioItem>1000.00</PrecioUnitarioItem>
      <SubtotalItem>1000.00</SubtotalItem>
    </Item>
  </DetalleItems>
</ECF>
"""


# ─── Helpers ───────────────────────────────────────────────────────────


def extraer_codigo_seguridad(signature_value: str) -> str:
    """Convierte SignatureValue (base64 std) a base64url sin padding y toma primeros 6 chars."""
    raw = base64.b64decode(signature_value)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()[:6]


@contextlib.contextmanager
def _temp_p12(p12_bytes: bytes):
    tmp = tempfile.NamedTemporaryFile(suffix=".p12", delete=False)
    try:
        tmp.write(p12_bytes)
        tmp.close()
        yield tmp.name
    finally:
        os.unlink(tmp.name)


# ─── Test 1: Carga del certificado ─────────────────────────────────────


class TestCargaCertificado:
    def test_private_key_extraida_sin_error(self, p12_bytes, p12_pin):
        key, cert, cas = pkcs12.load_key_and_certificates(p12_bytes, p12_pin)
        assert key is not None

    def test_certificado_cn_esperado(self, p12_bytes, p12_pin):
        _key, cert, _cas = pkcs12.load_key_and_certificates(p12_bytes, p12_pin)
        cn = cert.subject.rfc4514_string()
        assert "Test DGII Cert" in cn

    def test_pin_descifrado_con_fernet(self, p12_pin_encrypted, fernet_key):
        f = Fernet(fernet_key)
        pin_plano = f.decrypt(p12_pin_encrypted.encode()).decode()
        assert pin_plano == "test1234"


# ─── Test 2: Firma produce XML válido ──────────────────────────────────


class TestFirmaXML:
    def test_firma_produce_signature_node(self, p12_bytes, p12_pin):
        with _temp_p12(p12_bytes) as p12_path:
            from dgii.utils.xml_signer import sign_xml
            xml_firmado = sign_xml(MINIMAL_ECF_XML.encode(), p12_path, p12_pin.decode())
        root = etree.fromstring(xml_firmado)
        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        sig = root.find(".//ds:Signature", ns)
        assert sig is not None, "No se encontró el nodo <ds:Signature>"

    def test_firma_tiene_signaturevalue_no_vacio(self, p12_bytes, p12_pin):
        with _temp_p12(p12_bytes) as p12_path:
            from dgii.utils.xml_signer import sign_xml
            xml_firmado = sign_xml(MINIMAL_ECF_XML.encode(), p12_path, p12_pin.decode())
        root = etree.fromstring(xml_firmado)
        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        sv = root.find(".//ds:SignatureValue", ns)
        assert sv is not None
        assert sv.text is not None and sv.text.strip(), "SignatureValue vacío"


# ─── Test 2b: Factura real con build_ecf_xml ──────────────────────────


@pytest.fixture
def mock_comprobante():
    """Objeto simple con los atributos que build_ecf_xml necesita."""
    from datetime import datetime

    class MockDetalle:
        def __init__(self):
            self.numero_linea = 1
            self.descripcion = "Laptop Gamer"
            self.cantidad = 2
            self.precio_unitario = 45000.00
            self.subtotal = 90000.00

    class MockComprobante:
        xml_version = "1.0"
        tipo_ecf = 31
        encf = "E310000000042"
        rnc_emisor = "12345678901"
        fecha_emision = datetime(2026, 6, 7, 14, 30, 0)
        rnc_comprador = "10987654321"
        razon_social_comprador = "Comercial del Sur SRL"
        monto_gravado = 90000.00
        monto_exento = 0.00
        monto_itbis = 16200.00
        monto_total = 106200.00

    return MockComprobante(), [MockDetalle()]


class TestFacturaReal:
    """Usa build_ecf_xml() del proyecto para generar XML de factura real y lo firma."""

    def test_genera_y_firma_factura_real(self, p12_bytes, p12_pin, mock_comprobante, capsys):
        comprobante, detalles = mock_comprobante
        from dgii.utils.xml_builder import build_ecf_xml
        xml_bytes = build_ecf_xml(comprobante, detalles)

        with _temp_p12(p12_bytes) as p12_path:
            from dgii.utils.xml_signer import sign_xml
            xml_firmado = sign_xml(xml_bytes, p12_path, p12_pin.decode())

        root = etree.fromstring(xml_firmado)
        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        sig = root.find(".//ds:Signature", ns)
        assert sig is not None, "La factura real firmada no contiene <ds:Signature>"

        sv = root.find(".//ds:SignatureValue", ns)
        assert sv is not None
        assert sv.text and sv.text.strip()

        with capsys.disabled():
            print("\n" + "=" * 60)
            print("XML DE FACTURA REAL GENERADO (antes de firmar):")
            print("-" * 60)
            print(xml_bytes.decode("utf-8"))
            print("=" * 60)
            print("XML DE FACTURA REAL FIRMADO:")
            print("-" * 60)
            print(xml_firmado.decode("utf-8"))
            print("=" * 60)

    def test_factura_real_tiene_datos_correctos(self, p12_bytes, p12_pin, mock_comprobante):
        comprobante, detalles = mock_comprobante
        from dgii.utils.xml_builder import build_ecf_xml
        xml_bytes = build_ecf_xml(comprobante, detalles)

        with _temp_p12(p12_bytes) as p12_path:
            from dgii.utils.xml_signer import sign_xml
            xml_firmado = sign_xml(xml_bytes, p12_path, p12_pin.decode())

        root = etree.fromstring(xml_firmado)
        ns = {"ecf": "http://dgii.gov.do/ecf"}

        encf = root.xpath("string(//ecf:eNCF)", namespaces=ns)
        assert encf == "E310000000042"

        rnc = root.xpath("string(//ecf:RNCEmisor)", namespaces=ns)
        assert rnc == "12345678901"

        total = root.xpath("string(//ecf:Totales/ecf:MontoTotal)", namespaces=ns)
        assert float(total) == 106200.00

        desc = root.xpath("string(//ecf:DetalleItems/ecf:Item/ecf:NombreItem)", namespaces=ns)
        assert desc == "Laptop Gamer"


# ─── Test 3: codigo_seguridad_dgii se extrae correctamente ─────────────


class TestCodigoSeguridad:
    def test_primeros_6_caracteres_de_signaturevalue(self, p12_bytes, p12_pin):
        with _temp_p12(p12_bytes) as p12_path:
            from dgii.utils.xml_signer import sign_xml
            xml_firmado = sign_xml(MINIMAL_ECF_XML.encode(), p12_path, p12_pin.decode())
        root = etree.fromstring(xml_firmado)
        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        sv = root.find(".//ds:SignatureValue", ns)
        signature_value = sv.text.strip()
        codigo = extraer_codigo_seguridad(signature_value)
        assert len(codigo) == 6
        assert codigo.strip(), f"codigo_seguridad_dgii vacío: {codigo}"
        # base64url solo contiene [A-Za-z0-9_-]
        assert all(c.isalnum() or c in "-_" for c in codigo), (
            f"codigo_seguridad_dgii contiene caracteres inválidos: {codigo!r}"
        )


# ─── Test 4: certificado_usado se asigna ────────────────────────────────


class TestCertificadoUsado:
    def test_certificado_usado_asignado(self, db, empresa, p12_bytes, p12_pin, certificado_digital):
        from comprobantes.models import Comprobante
        comprobante = Comprobante.objects.create(
            empresa=empresa,
            rnc_emisor=empresa.rnc,
            tipo_ecf=31,
            monto_gravado=1000,
            monto_exento=0,
            monto_itbis=180,
            monto_total=1180,
        )
        with _temp_p12(p12_bytes) as p12_path:
            from dgii.utils.xml_signer import sign_xml
            xml_firmado = sign_xml(MINIMAL_ECF_XML.encode(), p12_path, p12_pin.decode())

        root = etree.fromstring(xml_firmado)
        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        sv = root.find(".//ds:SignatureValue", ns)

        comprobante.codigo_seguridad_dgii = sv.text.strip()[:6]
        comprobante.certificado_usado = certificado_digital
        comprobante.save(update_fields=["codigo_seguridad_dgii", "certificado_usado"])

        comprobante.refresh_from_db()
        assert comprobante.certificado_usado_id is not None
        assert comprobante.certificado_usado == certificado_digital
        assert comprobante.codigo_seguridad_dgii != ""


# ─── Test 5: XML mal formado falla antes de firmar ─────────────────────


class TestXMLMalFormado:
    def test_malformed_xml_lanza_excepcion(self):
        with pytest.raises(etree.XMLSyntaxError):
            etree.fromstring(b"<xml>esto no es valido")

    def test_sign_xml_malformado_lanza_excepcion(self, p12_bytes, p12_pin):
        with _temp_p12(p12_bytes) as p12_path:
            from dgii.utils.xml_signer import sign_xml
            with pytest.raises((etree.XMLSyntaxError, Exception)):
                sign_xml(b"no soy xml", p12_path, p12_pin.decode())

    def test_no_se_crea_dgiilog(self, db, p12_bytes, p12_pin):
        from dgii.models import DGIILog
        count_before = DGIILog.objects.count()
        with _temp_p12(p12_bytes) as p12_path:
            from dgii.utils.xml_signer import sign_xml
            try:
                sign_xml(b"no soy xml", p12_path, p12_pin.decode())
            except Exception:
                pass
        assert DGIILog.objects.count() == count_before, (
            "Se creó un DGIILog cuando no debía (sign_xml no debe crear logs)"
        )


# ─── Test: Crear XML Firmado desde Cero (todo en memoria) ─────────────


def test_crear_xml_firmado():
    """Recorre el pipeline completo: generar RSA → cert → PKCS12 → XML → firmar → verificar."""
    from datetime import datetime, timedelta, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID
    from lxml import etree
    import xmlsec

    PIN = b"test1234"

    # ── Paso 1: Generar clave RSA 2048 ────────────────────────────────
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # ── Paso 2: Certificado X.509 autofirmado ─────────────────────────
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-ecf")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256())
    )

    # ── Paso 3: Empacar en PKCS12 (en memoria) ────────────────────────
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"test-ecf",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(PIN),
    )

    # ── Paso 4: Construir XML con Id="ECF" ────────────────────────────
    NS = "http://dgii.gov.do/ecf"
    root = etree.Element(f"{{{NS}}}ECF", nsmap={None: NS})
    root.set("Id", "ECF")

    encabezado = etree.SubElement(root, f"{{{NS}}}Encabezado")
    iddoc = etree.SubElement(encabezado, f"{{{NS}}}IdDoc")
    etree.SubElement(iddoc, f"{{{NS}}}TipoeCF").text = "31"
    etree.SubElement(iddoc, f"{{{NS}}}eNCF").text = "E310000000001"

    # ── Paso 5: Extraer key y cert en PEM desde el PKCS12 ─────────────
    loaded_key, loaded_cert, _cas = pkcs12.load_key_and_certificates(p12_bytes, PIN)

    pem_key_bytes = loaded_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_cert_bytes = loaded_cert.public_bytes(encoding=serialization.Encoding.PEM)

    # ── Paso 6: Preparar nodo Signature ───────────────────────────────
    signature = xmlsec.template.create(
        root, xmlsec.Transform.EXCL_C14N, xmlsec.Transform.RSA_SHA256, ns="ds",
    )
    ref = xmlsec.template.add_reference(signature, xmlsec.Transform.SHA256, uri="#ECF")
    xmlsec.template.add_transform(ref, xmlsec.Transform.ENVELOPED)
    key_info = xmlsec.template.ensure_key_info(signature)
    xmlsec.template.add_x509_data(key_info)
    root.append(signature)

    # ── Paso 7: Firmar ────────────────────────────────────────────────
    xmlsec.tree.add_ids(root, ["Id"])

    ctx = xmlsec.SignatureContext()
    key = xmlsec.Key.from_memory(pem_key_bytes, xmlsec.KeyFormat.PEM)
    key.load_cert_from_memory(pem_cert_bytes, xmlsec.KeyFormat.CERT_PEM)
    ctx.key = key
    ctx.sign(signature)

    xml_firmado = etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    # ── Paso 8: Mostrar resultado ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("XML FIRMADO:")
    print("-" * 60)
    print(xml_firmado.decode("utf-8"))
    print("=" * 60)

    # ── Paso 9: Verificaciones ────────────────────────────────────────
    root_firmado = etree.fromstring(xml_firmado)
    ds_ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}

    # 8a. SignatureValue presente y no vacío
    sv = root_firmado.find(".//ds:SignatureValue", ds_ns)
    assert sv is not None, "No hay <ds:SignatureValue>"
    assert sv.text and sv.text.strip(), "<ds:SignatureValue> vacío"

    # 8b. Código de seguridad = base64 std → base64url sin padding → primeros 6 chars
    codigo = extraer_codigo_seguridad(sv.text.strip())
    print(f"SignatureValue (primeros 60 chars): {sv.text.strip()[:60]}...")
    print(f"codigo_seguridad_dgii (6 chars):    {codigo}")
    assert len(codigo) == 6
    assert codigo.strip(), f"codigo_seguridad_dgii vacío: {codigo!r}"
    # base64url solo contiene [A-Za-z0-9_-]
    assert all(c.isalnum() or c in "-_" for c in codigo), (
        f"codigo_seguridad_dgii contiene caracteres inválidos: {codigo!r}"
    )

    # 8c. Certificado X.509 embebido
    x509_cert = root_firmado.find(".//ds:X509Certificate", ds_ns)
    assert x509_cert is not None, "No hay <ds:X509Certificate>"
    assert x509_cert.text and x509_cert.text.strip()

    # 8d. Verificar criptográficamente la firma
    signature_node = root_firmado.find(".//ds:Signature", ds_ns)
    assert signature_node is not None

    xmlsec.tree.add_ids(root_firmado, ["Id"])
    vctx = xmlsec.SignatureContext()
    vkey = xmlsec.Key.from_memory(pem_key_bytes, xmlsec.KeyFormat.PEM)
    vkey.load_cert_from_memory(pem_cert_bytes, xmlsec.KeyFormat.CERT_PEM)
    vctx.key = vkey
    vctx.verify(signature_node)
    print("Firma verificada criptográficamente: OK")


# ─── Test 6: PIN incorrecto falla con excepción clara ──────────────────


class TestPINIncorrecto:
    def test_pin_incorrecto_lanza_excepcion(self, p12_bytes):
        with _temp_p12(p12_bytes) as p12_path:
            from dgii.utils.xml_signer import sign_xml
            with pytest.raises(Exception) as excinfo:
                sign_xml(MINIMAL_ECF_XML.encode(), p12_path, "wrong_pin_12345")
        assert excinfo.value is not None

    def test_mensaje_error_legible(self, p12_bytes):
        with _temp_p12(p12_bytes) as p12_path:
            from dgii.utils.xml_signer import sign_xml
            with pytest.raises(Exception) as excinfo:
                sign_xml(MINIMAL_ECF_XML.encode(), p12_path, "wrong_pin_12345")
        msg = str(excinfo.value)
        assert len(msg) > 0, "El mensaje de error está vacío"
        assert not msg.startswith("Traceback"), "El error es un traceback crudo"
