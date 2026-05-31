from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.pdfgen import canvas

from .models import Pago

ANCHO_80MM = 80 * mm
MARGEN_80MM = 4 * mm
ALTO_PAGINA_80MM = 150 * mm


def generar_pdf_a4(pago):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    c.setFont("Helvetica-Bold", 18)
    c.drawString(2 * cm, y, "COMPROBANTE DE PAGO")
    y -= 30

    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, f"Recibo No. REC-{pago.id}")
    y -= 20

    c.line(2 * cm, y, width - 2 * cm, y)
    y -= 25

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Empresa")
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, pago.empresa.razon_social)
    y -= 14
    c.drawString(2 * cm, y, f"RNC: {pago.empresa.rnc}")
    y -= 25

    c.line(2 * cm, y, width - 2 * cm, y)
    y -= 25

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Detalle del Pago")
    y -= 20

    datos = [
        ("Plan", pago.plan.nombre),
        ("Ciclo", pago.suscripcion.ciclo),
        ("Tipo", dict(Pago.TIPOS_PAGO).get(pago.tipo_pago, pago.tipo_pago)),
        ("Monto", f"{pago.monto} {pago.moneda}"),
        ("Metodo de pago", dict(Pago.METODOS_PAGO).get(pago.metodo_pago, pago.metodo_pago)),
        ("Referencia", pago.referencia or "\u2014"),
        ("Estado", "CONFIRMADO"),
        ("Confirmado por", pago.confirmado_por.email if pago.confirmado_por else "\u2014"),
        ("Fecha de pago", pago.fecha_pago.strftime("%d/%m/%Y %H:%M") if pago.fecha_pago else "\u2014"),
        ("Fecha de confirmacion",
         pago.fecha_confirmacion.strftime("%d/%m/%Y %H:%M") if pago.fecha_confirmacion else "\u2014"),
    ]

    c.setFont("Helvetica", 10)
    for label, value in datos:
        c.drawString(2 * cm, y, label)
        c.drawRightString(width - 2 * cm, y, str(value))
        y -= 16

    y -= 10
    c.line(2 * cm, y, width - 2 * cm, y)
    y -= 20

    c.setFont("Helvetica", 7)
    c.setFillGray(0.5)
    c.drawString(2 * cm, y, f"ID interno: {pago.id}")
    y -= 12
    c.drawString(2 * cm, y, "Este documento es un comprobante de pago interno.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def generar_pdf_80mm(pago):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(ANCHO_80MM, ALTO_PAGINA_80MM))
    x = MARGEN_80MM
    y = ALTO_PAGINA_80MM - MARGEN_80MM
    ancho_texto = ANCHO_80MM - 2 * MARGEN_80MM

    c.setFont("Courier-Bold", 10)
    c.drawCentredString(ANCHO_80MM / 2, y, "COMPROBANTE DE PAGO")
    y -= 16

    c.setFont("Courier", 8)
    c.drawCentredString(ANCHO_80MM / 2, y, f"REC-{pago.id}")
    y -= 20

    c.line(x, y, x + ancho_texto, y)
    y -= 14

    c.drawString(x, y, f"Empresa: {pago.empresa.razon_social}")
    y -= 12
    c.drawString(x, y, f"RNC: {pago.empresa.rnc}")
    y -= 16

    c.line(x, y, x + ancho_texto, y)
    y -= 14

    lineas = [
        f"Plan:      {pago.plan.nombre}",
        f"Ciclo:     {pago.suscripcion.ciclo}",
        f"Tipo:      {dict(Pago.TIPOS_PAGO).get(pago.tipo_pago, pago.tipo_pago)}",
        f"Metodo:    {dict(Pago.METODOS_PAGO).get(pago.metodo_pago, pago.metodo_pago)}",
        f"Refer.:    {pago.referencia or '-'}",
        f"Monto:     {pago.monto} {pago.moneda}",
        f"Estado:    CONFIRMADO",
    ]

    for linea in lineas:
        c.drawString(x, y, linea)
        y -= 12

    if pago.fecha_confirmacion:
        y -= 4
        c.line(x, y, x + ancho_texto, y)
        y -= 14
        c.drawString(
            x, y,
            f"Confirmado: {pago.confirmado_por.email if pago.confirmado_por else '--'}"
        )
        y -= 12
        c.drawString(
            x, y,
            f"Fecha: {pago.fecha_confirmacion.strftime('%d/%m/%Y %H:%M')}"
        )

    y -= 16
    c.line(x, y, x + ancho_texto, y)
    y -= 14

    c.setFont("Courier", 6)
    c.drawString(x, y, f"ID: {pago.id}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
