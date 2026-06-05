from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from empresas.models import Empresa
from comprobantes.models import Comprobante, ComprobanteDetalle


class ComprobanteCleanTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )

    def _base_comprobante(self, **kwargs):
        defaults = {
            "empresa": self.empresa,
            "tipo_ecf": 31,
            "rnc_comprador": "00123456789",
            "razon_social_comprador": "Cliente Test",
            "monto_gravado": Decimal("1000.00"),
            "monto_exento": Decimal("0.00"),
            "monto_itbis": Decimal("180.00"),
            "monto_total": Decimal("1180.00"),
        }
        defaults.update(kwargs)
        return Comprobante(**defaults)

    # --- E31: Crédito Fiscal ---

    def test_e31_sin_rnc_error(self):
        c = self._base_comprobante(tipo_ecf=31, rnc_comprador="")
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("rnc_comprador", str(ctx.exception))

    def test_e31_sin_razon_social_error(self):
        c = self._base_comprobante(tipo_ecf=31, razon_social_comprador="")
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("razon_social_comprador", str(ctx.exception))

    def test_e31_valido_pasa(self):
        c = self._base_comprobante(tipo_ecf=31)
        try:
            c.clean()
        except ValidationError:
            self.fail("E31 válido lanzó ValidationError")

    # --- E32: Consumo ---

    def test_e32_bajo_250k_sin_rnc_forza_consumidor_final(self):
        c = self._base_comprobante(
            tipo_ecf=32,
            rnc_comprador=None,
            monto_gravado=Decimal("50000.00"),
            monto_exento=Decimal("0.00"),
            monto_itbis=Decimal("9000.00"),
            monto_total=Decimal("59000.00"),
        )
        c.clean()
        self.assertEqual(c.razon_social_comprador, "CONSUMIDOR FINAL")

    def test_e32_sobre_250k_sin_rnc_error(self):
        c = self._base_comprobante(
            tipo_ecf=32,
            rnc_comprador=None,
            monto_gravado=Decimal("250000.00"),
            monto_exento=Decimal("0.00"),
            monto_itbis=Decimal("45000.00"),
            monto_total=Decimal("295000.00"),
        )
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("rnc_comprador", str(ctx.exception))

    # --- E33/E34: Notas ---

    def test_e33_sin_ncf_modificado_error(self):
        c = self._base_comprobante(tipo_ecf=33, ncf_modificado="")
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("ncf_modificado", str(ctx.exception))

    def test_e33_sin_codigo_modificacion_error(self):
        c = self._base_comprobante(
            tipo_ecf=33, ncf_modificado="E310000001", codigo_modificacion=None
        )
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("codigo_modificacion", str(ctx.exception))

    def test_e33_sin_razon_modificacion_error(self):
        c = self._base_comprobante(
            tipo_ecf=33,
            ncf_modificado="E310000001",
            codigo_modificacion=1,
            razon_modificacion="",
        )
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("razon_modificacion", str(ctx.exception))

    def test_e34_ncf_modificado_no_existe_error(self):
        c = self._base_comprobante(
            tipo_ecf=34,
            ncf_modificado="E3199999999",
            codigo_modificacion=1,
            razon_modificacion="Anulación total",
        )
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("ncf_modificado", str(ctx.exception))
        self.assertIn("no existe", str(ctx.exception))

    def test_e34_ncf_modificado_no_aceptado_error(self):
        original = self._base_comprobante(tipo_ecf=31, encf="E310000001")
        original.save()
        c = self._base_comprobante(
            tipo_ecf=34,
            ncf_modificado="E310000001",
            codigo_modificacion=1,
            razon_modificacion="Anulación",
        )
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("no está ACEPTADO", str(ctx.exception))

    def test_e33_rnc_no_coincide_error(self):
        original = self._base_comprobante(
            tipo_ecf=31,
            encf="E310000001",
            rnc_comprador="11111111111",
            razon_social_comprador="Original",
        )
        original.save()
        original.estado = Comprobante.ESTADO_ACEPTADO
        Comprobante.objects.filter(pk=original.pk).update(estado=Comprobante.ESTADO_ACEPTADO)

        c = self._base_comprobante(
            tipo_ecf=33,
            encf="E330000001",
            ncf_modificado="E310000001",
            codigo_modificacion=2,
            razon_modificacion="Corrección texto",
            rnc_comprador="22222222222",
            razon_social_comprador="Otro",
        )
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("debe coincidir", str(ctx.exception))

    def test_razon_modificacion_truncado_a_90(self):
        original = self._base_comprobante(
            tipo_ecf=31,
            encf="E310000001",
            rnc_comprador="00123456789",
            razon_social_comprador="Original",
        )
        original.save()
        Comprobante.objects.filter(pk=original.pk).update(estado=Comprobante.ESTADO_ACEPTADO)

        c = self._base_comprobante(
            tipo_ecf=33,
            ncf_modificado="E310000001",
            codigo_modificacion=2,
            razon_modificacion="X" * 200,
        )
        c.clean()
        self.assertLessEqual(len(c.razon_modificacion), 90)

    # --- Tipos fuera de Fase 1 ---

    def test_tipo_43_error(self):
        c = self._base_comprobante(tipo_ecf=43)
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("no soportado", str(ctx.exception))

    def test_tipo_44_error(self):
        c = self._base_comprobante(tipo_ecf=44)
        with self.assertRaises(ValidationError) as ctx:
            c.clean()
        self.assertIn("no soportado", str(ctx.exception))


class ComprobanteInmutabilidadTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )
        self.comprobante = Comprobante.objects.create(
            empresa=self.empresa,
            tipo_ecf=31,
            rnc_comprador="00123456789",
            razon_social_comprador="Cliente",
            rnc_emisor=self.empresa.rnc,
            encf="E310000001",
            estado=Comprobante.ESTADO_ACEPTADO,
            monto_gravado=Decimal("1000.00"),
            monto_exento=Decimal("0.00"),
            monto_itbis=Decimal("180.00"),
            monto_total=Decimal("1180.00"),
        )

    def test_puede_anularse_solo_borrador(self):
        c = Comprobante(estado=Comprobante.ESTADO_BORRADOR)
        self.assertTrue(c.puede_anularse)

    def test_no_puede_anularse_aceptado(self):
        self.assertFalse(self.comprobante.puede_anularse)

    def test_no_puede_modificar_aceptado(self):
        self.comprobante.monto_gravado = Decimal("2000.00")
        with self.assertRaises(ValidationError):
            self.comprobante.save()
