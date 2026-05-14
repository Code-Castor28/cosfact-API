"""
Firma basica de XML usando xmlsec.
"""
from lxml import etree
import xmlsec


def sign_xml(xml_bytes: bytes, cert_path: str, cert_pin: str) -> bytes:
    root = etree.fromstring(xml_bytes)

    signature_node = xmlsec.template.create(
        root,
        xmlsec.Transform.EXCL_C14N,
        xmlsec.Transform.RSA_SHA256,
        ns="ds",
    )
    root.append(signature_node)

    ref = xmlsec.template.add_reference(
        signature_node,
        xmlsec.Transform.SHA256,
        uri="",
    )
    xmlsec.template.add_transform(ref, xmlsec.Transform.ENVELOPED)

    key_info = xmlsec.template.ensure_key_info(signature_node)
    xmlsec.template.add_x509_data(key_info)

    ctx = xmlsec.SignatureContext()
    key = xmlsec.Key.from_file(cert_path, xmlsec.KeyFormat.PKCS12, cert_pin)
    ctx.key = key
    ctx.sign(signature_node)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
