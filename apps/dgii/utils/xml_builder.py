"""
Construccion basica de XML e-CF.
"""
from lxml import etree


def build_ecf_xml(comprobante, detalles):
    NS = "http://dgii.gov.do/ecf"
    root = etree.Element(f"{{{NS}}}ECF", attrib={"Id": "ECF"}, nsmap={None: NS})
    etree.SubElement(root, f"{{{NS}}}Version").text = comprobante.xml_version or "1.0"

    encabezado = etree.SubElement(root, f"{{{NS}}}Encabezado")

    iddoc = etree.SubElement(encabezado, f"{{{NS}}}IdDoc")
    etree.SubElement(iddoc, f"{{{NS}}}TipoeCF").text = str(comprobante.tipo_ecf)
    etree.SubElement(iddoc, f"{{{NS}}}eNCF").text = comprobante.encf or ""
    etree.SubElement(iddoc, f"{{{NS}}}FechaEmision").text = comprobante.fecha_emision.isoformat()

    emisor = etree.SubElement(encabezado, f"{{{NS}}}Emisor")
    etree.SubElement(emisor, f"{{{NS}}}RNCEmisor").text = comprobante.rnc_emisor or ""

    comprador = etree.SubElement(encabezado, f"{{{NS}}}Comprador")
    etree.SubElement(comprador, f"{{{NS}}}RNCComprador").text = comprobante.rnc_comprador or ""
    etree.SubElement(comprador, f"{{{NS}}}RazonSocialComprador").text = comprobante.razon_social_comprador or ""

    totales = etree.SubElement(encabezado, f"{{{NS}}}Totales")
    etree.SubElement(totales, f"{{{NS}}}MontoGravadoTotal").text = str(comprobante.monto_gravado)
    etree.SubElement(totales, f"{{{NS}}}MontoExento").text = str(comprobante.monto_exento)
    etree.SubElement(totales, f"{{{NS}}}TotalITBIS18").text = str(comprobante.monto_itbis)
    etree.SubElement(totales, f"{{{NS}}}MontoTotal").text = str(comprobante.monto_total)

    detalle_items = etree.SubElement(root, f"{{{NS}}}DetalleItems")
    for detalle in detalles:
        item = etree.SubElement(detalle_items, f"{{{NS}}}Item")
        etree.SubElement(item, f"{{{NS}}}NumeroLinea").text = str(detalle.numero_linea)
        etree.SubElement(item, f"{{{NS}}}NombreItem").text = detalle.descripcion
        etree.SubElement(item, f"{{{NS}}}CantidadItem").text = str(detalle.cantidad)
        etree.SubElement(item, f"{{{NS}}}PrecioUnitarioItem").text = str(detalle.precio_unitario)
        etree.SubElement(item, f"{{{NS}}}SubtotalItem").text = str(detalle.subtotal)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
