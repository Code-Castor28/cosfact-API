from django.test import TestCase
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import date

from empresas.models import Empresa, CertificadoDigital
from empresas.crypto import cifrar, descifrar


class CertificadoDigitalTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )

    def test_crear_certificado_digital(self):
        cert = CertificadoDigital.objects.create(
            empresa=self.empresa,
            alias="Certificado Producción",
            archivo=SimpleUploadedFile(
                "certificado.p12", b"fake-p12-content", content_type="application/x-pkcs12"
            ),
            pin_cifrado=cifrar("123456"),
            vigencia_desde=date(2026, 1, 1),
            vigencia_hasta=date(2027, 1, 1),
            activo=True,
        )
        self.assertEqual(cert.alias, "Certificado Producción")
        self.assertTrue(cert.activo)

    def test_pin_cifrado_descifrado(self):
        pin_original = "MiPinSeguro123"
        pin_cifrado = cifrar(pin_original)
        cert = CertificadoDigital.objects.create(
            empresa=self.empresa,
            alias="Test",
            archivo=SimpleUploadedFile(
                "test.p12", b"test", content_type="application/x-pkcs12"
            ),
            pin_cifrado=pin_cifrado,
            vigencia_desde=date(2026, 1, 1),
            vigencia_hasta=date(2027, 1, 1),
        )
        pin_descifrado = descifrar(cert.pin_cifrado)
        self.assertEqual(pin_descifrado, pin_original)

    def test_certificado_str(self):
        cert = CertificadoDigital.objects.create(
            empresa=self.empresa,
            alias="Mi Cert",
            archivo=SimpleUploadedFile(
                "test.p12", b"test", content_type="application/x-pkcs12"
            ),
            pin_cifrado=cifrar("1234"),
            vigencia_desde=date(2026, 1, 1),
            vigencia_hasta=date(2027, 1, 1),
        )
        self.assertIn("Mi Cert", str(cert))
        self.assertIn(self.empresa.rnc, str(cert))

    def test_certificado_activo_por_empresa(self):
        CertificadoDigital.objects.create(
            empresa=self.empresa,
            alias="Cert 1",
            archivo=SimpleUploadedFile("c1.p12", b"c1", content_type="application/x-pkcs12"),
            pin_cifrado=cifrar("1111"),
            vigencia_desde=date(2026, 1, 1),
            vigencia_hasta=date(2027, 1, 1),
        )
        CertificadoDigital.objects.create(
            empresa=self.empresa,
            alias="Cert 2",
            archivo=SimpleUploadedFile("c2.p12", b"c2", content_type="application/x-pkcs12"),
            pin_cifrado=cifrar("2222"),
            vigencia_desde=date(2026, 1, 1),
            vigencia_hasta=date(2027, 1, 1),
            activo=False,
        )
        activos = CertificadoDigital.objects.filter(empresa=self.empresa, activo=True)
        self.assertEqual(activos.count(), 1)
        self.assertEqual(activos.first().alias, "Cert 1")


class EmpresaCamposTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
            correo="contacto@empresa.com",
            telefono="8095550100",
            direccion="Calle Principal #123, Santo Domingo",
        )

    def test_campos_de_contacto(self):
        self.assertEqual(self.empresa.correo, "contacto@empresa.com")
        self.assertEqual(self.empresa.telefono, "8095550100")
        self.assertEqual(self.empresa.direccion, "Calle Principal #123, Santo Domingo")
