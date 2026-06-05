"""
Construccion basica de XML e-CF.
"""
from lxml import etree


def build_ecf_xml(comprobante, detalles):
    root = etree.Element("ECF")
    etree.SubElement(root, "Version").text = comprobante.xml_version or "1.0"

    encabezado = etree.SubElement(root, "Encabezado")
    etree.SubElement(encabezado, "Encf").text = comprobante.encf or ""
    etree.SubElement(encabezado, "RncEmisor").text = comprobante.rnc_emisor or ""
    etree.SubElement(encabezado, "FechaEmision").text = comprobante.fecha_emision.isoformat()
    etree.SubElement(encabezado, "RncComprador").text = comprobante.rnc_comprador or ""
    etree.SubElement(encabezado, "RazonSocialComprador").text = comprobante.razon_social_comprador or ""

    totales = etree.SubElement(root, "Totales")
    etree.SubElement(totales, "MontoGravado").text = str(comprobante.monto_gravado)
    etree.SubElement(totales, "MontoExento").text = str(comprobante.monto_exento)
    etree.SubElement(totales, "MontoItbis").text = str(comprobante.monto_itbis)
    etree.SubElement(totales, "MontoTotal").text = str(comprobante.monto_total)

    detalles_node = etree.SubElement(root, "Detalles")
    for detalle in detalles:
        detalle_node = etree.SubElement(detalles_node, "Detalle")
        etree.SubElement(detalle_node, "NumeroLinea").text = str(detalle.numero_linea)
        etree.SubElement(detalle_node, "Descripcion").text = detalle.descripcion
        etree.SubElement(detalle_node, "Cantidad").text = str(detalle.cantidad)
        etree.SubElement(detalle_node, "PrecioUnitario").text = str(detalle.precio_unitario)
        etree.SubElement(detalle_node, "Subtotal").text = str(detalle.subtotal)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
