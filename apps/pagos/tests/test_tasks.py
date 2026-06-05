"""
Tests unitarios para pagos.tasks.generar_pagos_automaticos.
"""
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone


# -- helpers ------------------------------------------------------------------

def _make_plan(
    precio_mensual=None,
    precio_anual=None,
    nombre="Plan Test",
):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.nombre = nombre
    plan.precio_mensual = Decimal(
        str(precio_mensual)) if precio_mensual is not None else None
    plan.precio_anual = Decimal(
        str(precio_anual)) if precio_anual is not None else None
    del plan.precio
    return plan


def _make_suscripcion(ciclo, plan, precio_pagado=None, empresa=None):
    from subscriptions.models import Suscripcion

    if empresa is None:
        empresa = MagicMock()
        empresa.id = uuid.uuid4()
        empresa.rnc = "123456789"

    sus = MagicMock(spec=Suscripcion)
    sus.id = uuid.uuid4()
    sus.ciclo = ciclo
    sus.plan = plan
    sus.empresa = empresa
    sus.empresa_id = empresa.id
    sus.precio_pagado = Decimal(
        str(precio_pagado)) if precio_pagado is not None else None
    sus.fecha_renovacion = timezone.now() + timedelta(days=10)
    return sus


# -- tests --------------------------------------------------------------------

class TestSeleccionarMonto(TestCase):
    """Tests directos de la funcion _seleccionar_monto."""

    def _call(self, suscripcion):
        from pagos.tasks import _seleccionar_monto
        return _seleccionar_monto(suscripcion)

    def test_mensual_usa_precio_mensual(self):
        plan = _make_plan(precio_mensual='1500.00', precio_anual='15000.00')
        sus = _make_suscripcion('MENSUAL', plan)
        self.assertEqual(self._call(sus), Decimal('1500.00'))

    def test_anual_usa_precio_anual(self):
        plan = _make_plan(precio_mensual='1500.00', precio_anual='15000.00')
        sus = _make_suscripcion('ANUAL', plan)
        self.assertEqual(self._call(sus), Decimal('15000.00'))

    def test_ciclo_monthly_alias(self):
        plan = _make_plan(precio_mensual='200.00')
        sus = _make_suscripcion('MONTHLY', plan)
        self.assertEqual(self._call(sus), Decimal('200.00'))

    def test_ciclo_annual_alias(self):
        plan = _make_plan(precio_anual='2400.00')
        sus = _make_suscripcion('ANNUAL', plan)
        self.assertEqual(self._call(sus), Decimal('2400.00'))

    def test_fallback_precio_pagado_cuando_plan_sin_precio_mensual(self):
        plan = _make_plan(precio_mensual=None, precio_anual=None)
        sus = _make_suscripcion('MENSUAL', plan, precio_pagado='999.00')
        self.assertEqual(self._call(sus), Decimal('999.00'))

    def test_fallback_precio_pagado_cuando_precio_mensual_cero(self):
        plan = _make_plan(precio_mensual='0', precio_anual='500.00')
        sus = _make_suscripcion('MENSUAL', plan, precio_pagado='750.00')
        self.assertEqual(self._call(sus), Decimal('750.00'))

    def test_ciclo_desconocido_usa_precio_mensual_primero(self):
        plan = _make_plan(precio_mensual='300.00', precio_anual='3000.00')
        sus = _make_suscripcion('SEMANAL', plan)
        self.assertEqual(self._call(sus), Decimal('300.00'))

    def test_ciclo_desconocido_fallback_a_precio_anual(self):
        plan = _make_plan(precio_mensual=None, precio_anual='3000.00')
        sus = _make_suscripcion('SEMANAL', plan)
        self.assertEqual(self._call(sus), Decimal('3000.00'))

    def test_sin_ninguna_fuente_retorna_none(self):
        plan = _make_plan(precio_mensual=None, precio_anual=None)
        sus = _make_suscripcion('MENSUAL', plan, precio_pagado=None)
        self.assertIsNone(self._call(sus))

    def test_precio_negativo_no_es_valido(self):
        plan = _make_plan(precio_mensual='-100')
        sus = _make_suscripcion('MENSUAL', plan, precio_pagado='500.00')
        self.assertEqual(self._call(sus), Decimal('500.00'))

    def test_precio_no_numerico_se_ignora(self):
        plan = _make_plan()
        plan.precio_mensual = 'no-es-numero'
        sus = _make_suscripcion('MENSUAL', plan, precio_pagado='400.00')
        self.assertEqual(self._call(sus), Decimal('400.00'))


class TestGenerarPagosAutomaticos(TestCase):
    """
    Tests de integracion liviana para generar_pagos_automaticos.
    Se mockean todos los accesos a DB.
    """

    def _run_task_with_suscripciones(
        self, suscripciones, *,
        existe_pendiente=False,
        existe_confirmado=True,
    ):
        from pagos.tasks import generar_pagos_automaticos

        qs_mock = MagicMock()
        qs_mock.__iter__ = MagicMock(return_value=iter(suscripciones))
        qs_mock.count.return_value = len(suscripciones)
        qs_mock.select_related.return_value = qs_mock

        pago_creado = MagicMock()
        pago_creado.id = uuid.uuid4()
        pago_creado.monto = Decimal('1500.00')
        pago_creado.moneda = 'DOP'

        with patch('pagos.tasks.Suscripcion.objects') as MockSusObjects, \
                patch('pagos.tasks.Pago') as MockPago, \
                patch('pagos.tasks.transaction') as MockTx:

            MockSusObjects.filter.return_value = qs_mock

            def filter_side_effect(**kwargs):
                f = MagicMock()
                if 'tipo_pago' in kwargs:
                    f.exists.return_value = existe_pendiente
                else:
                    f.exists.return_value = existe_confirmado
                return f

            MockPago.objects.filter.side_effect = filter_side_effect
            MockPago.objects.create.return_value = pago_creado
            MockPago.ESTADO_PENDIENTE = 'PENDIENTE'
            MockPago.ESTADO_CONFIRMADO = 'CONFIRMADO'
            MockPago.TIPO_RENOVACION = 'RENOVACION'
            MockPago.MONEDA_DOP = 'DOP'

            MockTx.atomic.return_value.__enter__ = MagicMock(return_value=None)
            MockTx.atomic.return_value.__exit__ = MagicMock(return_value=False)

            return generar_pagos_automaticos()

    def test_crea_pago_mensual(self):
        plan = _make_plan(precio_mensual='1500.00')
        sus = _make_suscripcion('MENSUAL', plan)
        resultado = self._run_task_with_suscripciones([sus])
        self.assertEqual(resultado['status'], 'success')
        self.assertEqual(resultado['pagos_creados'], 1)
        self.assertEqual(resultado['errores'], 0)

    def test_crea_pago_anual(self):
        plan = _make_plan(precio_anual='18000.00')
        sus = _make_suscripcion('ANUAL', plan)
        resultado = self._run_task_with_suscripciones([sus])
        self.assertEqual(resultado['status'], 'success')
        self.assertEqual(resultado['pagos_creados'], 1)

    def test_crea_pago_con_fallback_precio_pagado(self):
        plan = _make_plan()
        sus = _make_suscripcion('MENSUAL', plan, precio_pagado='800.00')
        resultado = self._run_task_with_suscripciones([sus])
        self.assertEqual(resultado['status'], 'success')
        self.assertEqual(resultado['pagos_creados'], 1)

    def test_salta_si_existe_pago_pendiente(self):
        plan = _make_plan(precio_mensual='1500.00')
        sus = _make_suscripcion('MENSUAL', plan)
        resultado = self._run_task_with_suscripciones(
            [sus], existe_pendiente=True)
        self.assertEqual(resultado['pagos_creados'], 0)
        self.assertEqual(resultado['saltados'], 1)
        self.assertEqual(resultado['errores'], 0)
        self.assertEqual(resultado['status'], 'no_action_needed')

    def test_salta_si_no_hay_pago_confirmado_previo(self):
        plan = _make_plan(precio_mensual='1500.00')
        sus = _make_suscripcion('MENSUAL', plan)
        resultado = self._run_task_with_suscripciones(
            [sus], existe_confirmado=False)
        self.assertEqual(resultado['pagos_creados'], 0)
        self.assertEqual(resultado['saltados'], 1)
        self.assertEqual(resultado['errores'], 0)
        self.assertEqual(resultado['status'], 'no_action_needed')

    def test_error_cuando_sin_ninguna_fuente_de_precio(self):
        plan = _make_plan()
        sus = _make_suscripcion('MENSUAL', plan, precio_pagado=None)
        resultado = self._run_task_with_suscripciones([sus])
        self.assertEqual(resultado['pagos_creados'], 0)
        self.assertEqual(resultado['errores'], 1)
        self.assertEqual(resultado['status'], 'failed')

    def test_status_partial_success(self):
        plan_ok = _make_plan(precio_mensual='1000.00')
        plan_bad = _make_plan()

        empresa_ok = MagicMock()
        empresa_ok.id = uuid.uuid4()
        empresa_ok.rnc = '111'
        empresa_bad = MagicMock()
        empresa_bad.id = uuid.uuid4()
        empresa_bad.rnc = '222'

        sus_ok = _make_suscripcion('MENSUAL', plan_ok, empresa=empresa_ok)
        sus_bad = _make_suscripcion('MENSUAL', plan_bad, empresa=empresa_bad)

        from pagos.tasks import generar_pagos_automaticos

        qs_mock = MagicMock()
        qs_mock.__iter__ = MagicMock(return_value=iter([sus_ok, sus_bad]))
        qs_mock.count.return_value = 2
        qs_mock.select_related.return_value = qs_mock

        pago_creado = MagicMock()
        pago_creado.id = uuid.uuid4()
        pago_creado.monto = Decimal('1000.00')
        pago_creado.moneda = 'DOP'

        with patch('pagos.tasks.Suscripcion.objects') as MockSusObjects, \
                patch('pagos.tasks.Pago') as MockPago, \
                patch('pagos.tasks.transaction') as MockTx:

            MockSusObjects.filter.return_value = qs_mock

            def filter_side_effect(**kwargs):
                f = MagicMock()
                f.exists.return_value = 'tipo_pago' not in kwargs
                return f

            MockPago.objects.filter.side_effect = filter_side_effect
            MockPago.objects.create.return_value = pago_creado
            MockPago.ESTADO_PENDIENTE = 'PENDIENTE'
            MockPago.ESTADO_CONFIRMADO = 'CONFIRMADO'
            MockPago.TIPO_RENOVACION = 'RENOVACION'
            MockPago.MONEDA_DOP = 'DOP'

            MockTx.atomic.return_value.__enter__ = MagicMock(return_value=None)
            MockTx.atomic.return_value.__exit__ = MagicMock(return_value=False)

            resultado = generar_pagos_automaticos()

        self.assertEqual(resultado['status'], 'partial_success')
        self.assertEqual(resultado['pagos_creados'], 1)
        self.assertEqual(resultado['errores'], 1)

    def test_sin_suscripciones_retorna_no_action_needed(self):
        resultado = self._run_task_with_suscripciones([])
        self.assertEqual(resultado['status'], 'no_action_needed')
        self.assertEqual(resultado['pagos_creados'], 0)
        self.assertEqual(resultado['errores'], 0)
