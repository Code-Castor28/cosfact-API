from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from apps.pagos.models import Pago
from subscriptions.models import Plan, Suscripcion
from empresas.models import Empresa

from apps.pagos.tasks import generar_pagos_automaticos


class GenerarPagosAutomaticosTests(TestCase):
    def setUp(self):
        # Empresa
        self.empresa = Empresa.objects.create(
            rnc='34567893211',
            razon_social='Cliente Test'
        )

        # Plan con precios válidos
        self.plan = Plan.objects.create(
            nombre='Basico',
            descripcion='Plan de prueba',
            limite_comprobantes=10,
            precio_mensual=Decimal('1000.00'),
            precio_anual=Decimal('10000.00'),
            ciclo_disponible=Plan.CICLO_AMBOS,
        )

    def _create_suscripcion(self, ciclo):
        hoy = timezone.now().date()
        sus = Suscripcion.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            ciclo=ciclo,
            estado=Suscripcion.ESTADO_ACTIVA,
            fecha_inicio=hoy - timedelta(days=30),
            fecha_renovacion=hoy + timedelta(days=5),
            precio_pagado=Decimal('0.00'),
        )
        return sus

    def test_generar_pagos_crea_pago_mensual(self):
        sus = self._create_suscripcion(Suscripcion.CICLO_MENSUAL)

        resultado = generar_pagos_automaticos()

        # Verificar que se creó un Pago PENDIENTE para la empresa
        pagos = Pago.objects.filter(empresa=self.empresa, estado=Pago.ESTADO_PENDIENTE)
        self.assertEqual(pagos.count(), 1)
        pago = pagos.first()
        self.assertEqual(pago.monto, self.plan.precio_mensual)

    def test_generar_pagos_crea_pago_anual(self):
        sus = self._create_suscripcion(Suscripcion.CICLO_ANUAL)

        resultado = generar_pagos_automaticos()

        pagos = Pago.objects.filter(empresa=self.empresa, estado=Pago.ESTADO_PENDIENTE)
        self.assertEqual(pagos.count(), 1)
        pago = pagos.first()
        self.assertEqual(pago.monto, self.plan.precio_anual)
