from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


class GenerarPagosAutomaticosTests(TestCase):
    def setUp(self):
        # Import models here to ensure Django app registry is ready
        from empresas.models import Empresa
        from subscriptions.models import Plan, Suscripcion

        # Save classes for reuse
        self.Empresa = Empresa
        self.Plan = Plan
        self.Suscripcion = Suscripcion

        # Crear empresa y plan de prueba
        self.empresa = self.Empresa.objects.create(
            rnc='34567893211',
            razon_social='Cliente Test'
        )

        self.plan = self.Plan.objects.create(
            nombre='Basico',
            descripcion='Plan de prueba',
            limite_comprobantes=10,
            precio_mensual=Decimal('1000.00'),
            precio_anual=Decimal('10000.00'),
            ciclo_disponible=self.Plan.CICLO_AMBOS,
        )

    def _create_suscripcion(self, ciclo):
        hoy = timezone.now().date()
        sus = self.Suscripcion.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            ciclo=ciclo,
            estado=self.Suscripcion.ESTADO_ACTIVA,
            fecha_inicio=hoy - timedelta(days=30),
            fecha_renovacion=hoy + timedelta(days=5),
            precio_pagado=Decimal('0.00'),
        )
        return sus

    def test_generar_pagos_crea_pago_mensual(self):
        # Import Pago and task here to avoid early model import
        from pagos.models import Pago
        from pagos.tasks import generar_pagos_automaticos

        sus = self._create_suscripcion(self.Suscripcion.CICLO_MENSUAL)

        resultado = generar_pagos_automaticos()

        # Verificar que se creó un Pago PENDIENTE para la empresa
        pagos = Pago.objects.filter(
            empresa=self.empresa, estado=Pago.ESTADO_PENDIENTE)
        self.assertEqual(pagos.count(), 1)
        pago = pagos.first()
        self.assertEqual(pago.monto, self.plan.precio_mensual)

    def test_generar_pagos_crea_pago_anual(self):
        from pagos.models import Pago
        from pagos.tasks import generar_pagos_automaticos

        sus = self._create_suscripcion(self.Suscripcion.CICLO_ANUAL)

        resultado = generar_pagos_automaticos()

        pagos = Pago.objects.filter(
            empresa=self.empresa, estado=Pago.ESTADO_PENDIENTE)
        self.assertEqual(pagos.count(), 1)
        pago = pagos.first()
        self.assertEqual(pago.monto, self.plan.precio_anual)
