from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from empresas.models import Empresa
from .models import Plan, Suscripcion, PaqueteComprobantes


class PlanModelTest(TestCase):
    def test_crear_plan_minimo(self):
        plan = Plan.objects.create(
            nombre="Plan Básico",
            limite_comprobantes=500,
            precio_mensual=Decimal("500.00"),
            ciclo_disponible=Plan.CICLO_MENSUAL,
        )
        self.assertEqual(plan.nombre, "Plan Básico")
        self.assertEqual(plan.limite_comprobantes, 500)
        self.assertTrue(plan.activo)

    def test_plan_mensual_sin_precio_error(self):
        plan = Plan(
            nombre="Plan Sin Precio",
            limite_comprobantes=100,
            ciclo_disponible=Plan.CICLO_MENSUAL,
            precio_mensual=None,
        )
        with self.assertRaises(ValidationError) as ctx:
            plan.clean()
        self.assertIn("precio_mensual", str(ctx.exception))

    def test_plan_anual_sin_precio_error(self):
        plan = Plan(
            nombre="Plan Sin Precio Anual",
            limite_comprobantes=100,
            ciclo_disponible=Plan.CICLO_ANUAL,
            precio_anual=None,
        )
        with self.assertRaises(ValidationError) as ctx:
            plan.clean()
        self.assertIn("precio_anual", str(ctx.exception))

    def test_plan_ambos_sin_precios_error(self):
        plan = Plan(
            nombre="Plan Sin Precios",
            limite_comprobantes=100,
            ciclo_disponible=Plan.CICLO_AMBOS,
        )
        with self.assertRaises(ValidationError):
            plan.clean()


class SuscripcionModelTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )
        self.plan = Plan.objects.create(
            nombre="Plan Básico",
            limite_comprobantes=500,
            precio_mensual=Decimal("500.00"),
            ciclo_disponible=Plan.CICLO_MENSUAL,
            dias_gracia=5,
        )

    def test_suscripcion_activa(self):
        suscripcion = Suscripcion.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            ciclo=Suscripcion.CICLO_MENSUAL,
            fecha_inicio=timezone.now().date() - timedelta(days=10),
            fecha_renovacion=timezone.now().date() + timedelta(days=20),
        )
        self.assertTrue(suscripcion.esta_activa)

    def test_suscripcion_vencida_sin_gracia(self):
        self.plan.dias_gracia = 0
        self.plan.save()
        suscripcion = Suscripcion.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            ciclo=Suscripcion.CICLO_MENSUAL,
            fecha_inicio=timezone.now().date() - timedelta(days=60),
            fecha_renovacion=timezone.now().date() - timedelta(days=1),
        )
        self.assertFalse(suscripcion.esta_activa)

    def test_suscripcion_en_gracia(self):
        suscripcion = Suscripcion.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            ciclo=Suscripcion.CICLO_MENSUAL,
            fecha_inicio=timezone.now().date() - timedelta(days=30),
            fecha_renovacion=timezone.now().date() - timedelta(days=2),
        )
        self.assertTrue(suscripcion.esta_activa)

    def test_suscripcion_fuera_gracia(self):
        suscripcion = Suscripcion.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            ciclo=Suscripcion.CICLO_MENSUAL,
            fecha_inicio=timezone.now().date() - timedelta(days=30),
            fecha_renovacion=timezone.now().date() - timedelta(days=10),
        )
        self.assertFalse(suscripcion.esta_activa)

    def test_suscripcion_cancelada_no_activa(self):
        suscripcion = Suscripcion.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            ciclo=Suscripcion.CICLO_MENSUAL,
            fecha_inicio=timezone.now().date(),
            fecha_renovacion=timezone.now().date() + timedelta(days=30),
            estado=Suscripcion.ESTADO_CANCELADA,
        )
        self.assertFalse(suscripcion.esta_activa)


class PaqueteComprobantesTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )
        self.plan = Plan.objects.create(
            nombre="Plan Básico",
            limite_comprobantes=500,
            precio_mensual=Decimal("500.00"),
            ciclo_disponible=Plan.CICLO_MENSUAL,
        )

    def test_crear_paquete(self):
        paquete = PaqueteComprobantes.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            total_comprobantes=100,
        )
        self.assertEqual(paquete.comprobantes_restantes, 100)
        self.assertTrue(paquete.disponible)
        self.assertEqual(paquete.estado, PaqueteComprobantes.ESTADO_ACTIVO)

    def test_consumir_comprobante_exitoso(self):
        paquete = PaqueteComprobantes.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            total_comprobantes=10,
        )
        with transaction.atomic():
            p = PaqueteComprobantes.objects.select_for_update().get(pk=paquete.pk)
            self.assertTrue(p.consumir_comprobante())
        p.refresh_from_db()
        self.assertEqual(p.comprobantes_usados, 1)
        self.assertEqual(p.comprobantes_restantes, 9)

    def test_consumir_comprobante_agota_paquete(self):
        paquete = PaqueteComprobantes.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            total_comprobantes=1,
        )
        with transaction.atomic():
            p = PaqueteComprobantes.objects.select_for_update().get(pk=paquete.pk)
            self.assertTrue(p.consumir_comprobante())
        p.refresh_from_db()
        self.assertEqual(p.estado, PaqueteComprobantes.ESTADO_AGOTADO)
        self.assertFalse(p.disponible)

    def test_consumir_comprobante_paquete_agotado_false(self):
        paquete = PaqueteComprobantes.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            total_comprobantes=0,
            estado=PaqueteComprobantes.ESTADO_AGOTADO,
        )
        self.assertFalse(paquete.disponible)
        with transaction.atomic():
            p = PaqueteComprobantes.objects.select_for_update().get(pk=paquete.pk)
            self.assertFalse(p.consumir_comprobante())

    def test_revertir_consumo_restaura_paquete(self):
        paquete = PaqueteComprobantes.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            total_comprobantes=1,
        )
        with transaction.atomic():
            p = PaqueteComprobantes.objects.select_for_update().get(pk=paquete.pk)
            p.consumir_comprobante()
        with transaction.atomic():
            p = PaqueteComprobantes.objects.select_for_update().get(pk=paquete.pk)
            p.revertir_consumo()
        p.refresh_from_db()
        self.assertEqual(p.comprobantes_usados, 0)
        self.assertEqual(p.estado, PaqueteComprobantes.ESTADO_ACTIVO)

    def test_revertir_consumo_sin_consumo_previo(self):
        paquete = PaqueteComprobantes.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            total_comprobantes=10,
        )
        with transaction.atomic():
            p = PaqueteComprobantes.objects.select_for_update().get(pk=paquete.pk)
            p.revertir_consumo()
        p.refresh_from_db()
        self.assertEqual(p.comprobantes_usados, 0)

    def test_paquete_clean_excede_plan_error(self):
        paquete = PaqueteComprobantes(
            empresa=self.empresa,
            plan=self.plan,
            total_comprobantes=999999,
        )
        with self.assertRaises(ValidationError) as ctx:
            paquete.clean()
        self.assertIn("total_comprobantes", str(ctx.exception))

    def test_paquete_fifo_ordering(self):
        p1 = PaqueteComprobantes.objects.create(
            empresa=self.empresa, plan=self.plan, total_comprobantes=10,
        )
        p2 = PaqueteComprobantes.objects.create(
            empresa=self.empresa, plan=self.plan, total_comprobantes=20,
        )
        paquetes = list(PaqueteComprobantes.objects.all())
        self.assertEqual(paquetes[0].pk, p1.pk)
        self.assertEqual(paquetes[1].pk, p2.pk)

    def test_paquete_vencido_no_disponible(self):
        paquete = PaqueteComprobantes.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            total_comprobantes=10,
            fecha_vencimiento=timezone.now() - timedelta(days=1),
            estado=PaqueteComprobantes.ESTADO_ACTIVO,
        )
        self.assertFalse(paquete.disponible)

    def test_paquete_cancelado_no_disponible(self):
        paquete = PaqueteComprobantes.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            total_comprobantes=10,
            estado=PaqueteComprobantes.ESTADO_CANCELADO,
        )
        self.assertFalse(paquete.disponible)
