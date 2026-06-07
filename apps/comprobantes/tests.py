from django.core.exceptions import ValidationError
from django.test import TestCase
from unittest.mock import MagicMock, patch

from .models import Comprobante


class TestEstadoDGIIMachine(TestCase):
    """Transiciones de estado_dgii — lógica pura sin DB."""

    def _validar(self, desde, hasta, debe_funcionar=True):
        try:
            mock = MagicMock(spec=Comprobante)
            mock.pk = True
            mock.estado_dgii = hasta
            transiciones = Comprobante.TRANSICIONES_ESTADO_DGII
            permitidas = transiciones.get(desde, set())
            if hasta not in permitidas:
                raise ValidationError("invalida")
            return True
        except ValidationError:
            if debe_funcionar:
                raise
            return False

    def test_sin_enviar_a_enviado(self):
        assert self._validar("SIN_ENVIAR", "ENVIADO")

    def test_enviado_a_aceptado(self):
        assert self._validar("ENVIADO", "ACEPTADO")

    def test_enviado_a_rechazado(self):
        assert self._validar("ENVIADO", "RECHAZADO")

    def test_enviado_a_contingencia(self):
        assert self._validar("ENVIADO", "CONTINGENCIA")

    def test_enviado_a_error_red(self):
        assert self._validar("ENVIADO", "ERROR_RED")

    def test_rechazado_a_reintentando(self):
        assert self._validar("RECHAZADO", "REINTENTANDO")

    def test_contingencia_a_reintentando(self):
        assert self._validar("CONTINGENCIA", "REINTENTANDO")

    def test_error_red_a_reintentando(self):
        assert self._validar("ERROR_RED", "REINTENTANDO")

    def test_reintentando_a_enviado(self):
        assert self._validar("REINTENTANDO", "ENVIADO")

    def test_aceptado_es_terminal(self):
        transiciones = Comprobante.TRANSICIONES_ESTADO_DGII
        assert transiciones.get("ACEPTADO") == set()

    def test_aceptado_no_puede_ir_a_rechazado(self):
        assert not self._validar("ACEPTADO", "RECHAZADO", debe_funcionar=False)

    def test_aceptado_no_puede_ir_a_reintentando(self):
        assert not self._validar("ACEPTADO", "REINTENTANDO", debe_funcionar=False)

    def test_sin_enviar_no_puede_ir_a_aceptado(self):
        assert not self._validar("SIN_ENVIAR", "ACEPTADO", debe_funcionar=False)

    def test_sin_enviar_no_puede_ir_a_reintentando(self):
        assert not self._validar("SIN_ENVIAR", "REINTENTANDO", debe_funcionar=False)

    def test_rechazado_no_puede_ir_a_aceptado_directo(self):
        assert not self._validar("RECHAZADO", "ACEPTADO", debe_funcionar=False)

    def test_reintentando_no_puede_ir_a_aceptado_directo(self):
        assert not self._validar("REINTENTANDO", "ACEPTADO", debe_funcionar=False)

    def test_transiciones_estado_con_emitido(self):
        transiciones = Comprobante.TRANSICIONES_PERMITIDAS
        assert "EMITIDO" in transiciones.get("BORRADOR")

    def test_emitido_puede_ir_a_contingencia(self):
        transiciones = Comprobante.TRANSICIONES_PERMITIDAS
        assert "CONTINGENCIA" in transiciones.get("EMITIDO")

    def test_emitido_puede_ir_a_anulado(self):
        transiciones = Comprobante.TRANSICIONES_PERMITIDAS
        assert "ANULADO" in transiciones.get("EMITIDO")


class TestEstadoDGIIMachineSave(TestCase):
    """Validación real a través de save() — requiere DB."""

    def setUp(self):
        from empresas.models import Empresa
        self.empresa = Empresa.objects.create(
            rnc="999999999",
            razon_social="Test SA",
            ambiente="testecf",
            correo="test@test.com",
        )

    def _crear_comprobante(self, **kwargs):
        valores = dict(
            empresa=self.empresa,
            tipo_ecf=32,
            rnc_emisor=self.empresa.rnc,
            monto_total=1000,
            estado=Comprobante.ESTADO_BORRADOR,
            estado_dgii=Comprobante.ESTADO_DGII_SIN_ENVIAR,
        )
        valores.update(kwargs)
        return Comprobante.objects.create(**valores)

    def test_crear_con_sin_enviar_por_defecto(self):
        c = self._crear_comprobante()
        assert c.estado_dgii == Comprobante.ESTADO_DGII_SIN_ENVIAR

    def test_mutar_a_enviado_ok(self):
        c = self._crear_comprobante()
        c.estado_dgii = Comprobante.ESTADO_DGII_ENVIADO
        c.estado = Comprobante.ESTADO_EMITIDO
        c.save()
        assert c.estado_dgii == Comprobante.ESTADO_DGII_ENVIADO

    def test_emitido_ok(self):
        c = self._crear_comprobante()
        c.estado = Comprobante.ESTADO_EMITIDO
        c.estado_dgii = Comprobante.ESTADO_DGII_ENVIADO
        c.save()
        assert c.estado == Comprobante.ESTADO_EMITIDO

    def test_saltar_directo_a_aceptado_rechazado(self):
        c = self._crear_comprobante()
        c.estado = Comprobante.ESTADO_EMITIDO
        c.estado_dgii = Comprobante.ESTADO_DGII_ENVIADO
        c.save()
        c.estado_dgii = Comprobante.ESTADO_DGII_ACEPTADO
        c.save()
        assert c.estado_dgii == "ACEPTADO"

    def test_transicion_invalida_lanza_error(self):
        c = self._crear_comprobante()
        c.estado = Comprobante.ESTADO_EMITIDO
        c.estado_dgii = Comprobante.ESTADO_DGII_ENVIADO
        c.save()
        c.estado_dgii = Comprobante.ESTADO_DGII_ACEPTADO
        c.save()
        c.estado_dgii = Comprobante.ESTADO_DGII_RECHAZADO
        with self.assertRaises(ValidationError):
            c.save()

    def test_aceptado_terminal_no_permite_mas_cambios(self):
        c = self._crear_comprobante()
        c.estado = Comprobante.ESTADO_EMITIDO
        c.estado_dgii = Comprobante.ESTADO_DGII_ENVIADO
        c.save()
        c.estado_dgii = Comprobante.ESTADO_DGII_ACEPTADO
        c.save()
        for destino in [Comprobante.ESTADO_DGII_RECHAZADO,
                        Comprobante.ESTADO_DGII_CONTINGENCIA,
                        Comprobante.ESTADO_DGII_REINTENTANDO,
                        Comprobante.ESTADO_DGII_ERROR_RED]:
            c.estado_dgii = destino
            with self.assertRaises(ValidationError):
                c.save()
