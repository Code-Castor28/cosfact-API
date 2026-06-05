from unittest.mock import patch
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import transaction
from empresas.models import Empresa
from subscriptions.models import Plan, Suscripcion, PaqueteComprobantes
from .models import Secuencial, NumeroViciado, MovimientoSecuencial
from .services import (
    obtener_proximo_encf, SecuencialAgotadoError,
    TipoECFBloqueadoError, TipoECFNoExisteError,
)


class SecuencialModelTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )

    def test_crear_secuencial_valido(self):
        s = Secuencial.objects.create(
            empresa=self.empresa,
            tipo_ecf=31,
            minimo_asignado=1,
            maximo_asignado=100,
        )
        self.assertEqual(s.ultimo_numero, 0)
        self.assertFalse(s.bloqueado)
        self.assertEqual(s.porcentaje_uso, 0.0)

    def test_proximo_encf_no_incrementa(self):
        s = Secuencial.objects.create(
            empresa=self.empresa,
            tipo_ecf=31,
            minimo_asignado=1,
            maximo_asignado=100,
        )
        encf = s.proximo_encf()
        self.assertEqual(encf, "E3100000001")
        s.refresh_from_db()
        self.assertEqual(s.ultimo_numero, 0)

    def test_porcentaje_uso(self):
        s = Secuencial.objects.create(
            empresa=self.empresa,
            tipo_ecf=31,
            ultimo_numero=50,
            minimo_asignado=1,
            maximo_asignado=100,
        )
        self.assertEqual(s.porcentaje_uso, 50.0)

    def test_casi_agotado_true(self):
        s = Secuencial.objects.create(
            empresa=self.empresa,
            tipo_ecf=31,
            ultimo_numero=90,
            minimo_asignado=1,
            maximo_asignado=100,
        )
        self.assertTrue(s.casi_agotado)

    def test_casi_agotado_false(self):
        s = Secuencial.objects.create(
            empresa=self.empresa,
            tipo_ecf=31,
            ultimo_numero=50,
            minimo_asignado=1,
            maximo_asignado=100,
        )
        self.assertFalse(s.casi_agotado)

    def test_clean_minimo_menor_1_error(self):
        s = Secuencial(
            empresa=self.empresa, tipo_ecf=31,
            minimo_asignado=0, maximo_asignado=100,
        )
        with self.assertRaises(ValidationError) as ctx:
            s.clean()
        self.assertIn("minimo_asignado", str(ctx.exception))

    def test_clean_maximo_menor_igual_minimo_error(self):
        s = Secuencial(
            empresa=self.empresa, tipo_ecf=31,
            minimo_asignado=50, maximo_asignado=50,
        )
        with self.assertRaises(ValidationError) as ctx:
            s.clean()
        self.assertIn("maximo_asignado", str(ctx.exception))

    def test_clean_ultimo_numero_excede_maximo_error(self):
        s = Secuencial(
            empresa=self.empresa, tipo_ecf=31,
            ultimo_numero=101, minimo_asignado=1, maximo_asignado=100,
        )
        with self.assertRaises(ValidationError) as ctx:
            s.clean()
        self.assertIn("ultimo_numero", str(ctx.exception))

    def test_formatear_encf(self):
        s = Secuencial(empresa=self.empresa, tipo_ecf=31)
        encf = s._formatear_encf(1)
        self.assertEqual(encf, "E3100000001")

    def test_formatear_encf_tipo_41(self):
        s = Secuencial(empresa=self.empresa, tipo_ecf=41)
        encf = s._formatear_encf(123)
        self.assertEqual(encf, "E4100000123")

    def test_unique_constraint_empresa_tipo(self):
        Secuencial.objects.create(empresa=self.empresa, tipo_ecf=31)
        with self.assertRaises(Exception):
            Secuencial.objects.create(empresa=self.empresa, tipo_ecf=31)


class SecuencialServiceTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )
        self.secuencial = Secuencial.objects.create(
            empresa=self.empresa,
            tipo_ecf=31,
            minimo_asignado=1,
            maximo_asignado=10,
        )

    def test_obtener_proximo_encf_exitoso(self):
        encf = obtener_proximo_encf(self.empresa, 31)
        self.assertEqual(encf, "E3100000001")
        self.secuencial.refresh_from_db()
        self.assertEqual(self.secuencial.ultimo_numero, 1)

    def test_obtener_proximo_encf_incrementa_secuencialmente(self):
        e1 = obtener_proximo_encf(self.empresa, 31)
        e2 = obtener_proximo_encf(self.empresa, 31)
        self.assertEqual(e1, "E3100000001")
        self.assertEqual(e2, "E3100000002")

    def test_obtener_proximo_encf_crea_movimiento(self):
        encf = obtener_proximo_encf(self.empresa, 31)
        movimiento = MovimientoSecuencial.objects.filter(
            empresa=self.empresa, tipo_ecf=31
        ).first()
        self.assertIsNotNone(movimiento)
        self.assertEqual(movimiento.encf_generado, encf)
        self.assertEqual(movimiento.numero_asignado, 1)

    def test_obtener_proximo_encf_sin_secuencial_error(self):
        with self.assertRaises(TipoECFNoExisteError):
            obtener_proximo_encf(self.empresa, 41)

    def test_obtener_proximo_encf_bloqueado_error(self):
        self.secuencial.bloqueado = True
        self.secuencial.motivo_bloqueo = "Mantenimiento"
        self.secuencial.save()
        with self.assertRaises(TipoECFBloqueadoError):
            obtener_proximo_encf(self.empresa, 31)

    def test_obtener_proximo_encf_agotado_error(self):
        self.secuencial.ultimo_numero = 10
        self.secuencial.save()
        with self.assertRaises(SecuencialAgotadoError):
            obtener_proximo_encf(self.empresa, 31)

    def test_obtener_proximo_encf_agotado_bloquea_auto(self):
        self.secuencial.ultimo_numero = 10
        self.secuencial.save()
        try:
            obtener_proximo_encf(self.empresa, 31)
        except SecuencialAgotadoError:
            pass
        self.secuencial.refresh_from_db()
        self.assertTrue(self.secuencial.bloqueado)
        self.assertIn("agotado", self.secuencial.motivo_bloqueo.lower())

    def test_obtener_proximo_encf_tipo_invalido(self):
        with self.assertRaises(ValueError):
            obtener_proximo_encf(self.empresa, 99)


class NumeroViciadoTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )

    def test_crear_numero_viciado(self):
        nv = NumeroViciado.objects.create(
            empresa=self.empresa,
            encf="E310000001",
            motivo="Rechazado por DGII",
        )
        self.assertEqual(nv.encf, "E310000001")
        self.assertIsNotNone(nv.viciado_at)

    def test_unique_empresa_encf(self):
        NumeroViciado.objects.create(
            empresa=self.empresa, encf="E310000001", motivo="Test"
        )
        with self.assertRaises(Exception):
            NumeroViciado.objects.create(
                empresa=self.empresa, encf="E310000001", motivo="Duplicado"
            )


class SaaSGuardOnboardingTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )
        self.plan = Plan.objects.create(
            nombre="Plan Básico",
            limite_comprobantes=1000,
            precio_mensual=Decimal("500.00"),
            ciclo_disponible=Plan.CICLO_MENSUAL,
        )
        from django.utils import timezone
        self.suscripcion = Suscripcion.objects.create(
            empresa=self.empresa,
            plan=self.plan,
            ciclo=Suscripcion.CICLO_MENSUAL,
            fecha_inicio=timezone.now().date() - timezone.timedelta(days=30),
            fecha_renovacion=timezone.now().date() + timezone.timedelta(days=30),
        )

    def test_validar_volumen_no_excede_limite(self):
        from sequences.views import onboarding
        from rest_framework.test import APIRequestFactory
        from rest_framework.test import force_authenticate
        from users.models import Usuario

        usuario = Usuario.objects.create_user(
            email="admin@test.com", password="Test123456",
            nombre="Admin", apellido="Test",
            empresa=self.empresa, rol=Usuario.ROL_SUPERADMIN,
        )

        data = {
            "secuencias": [
                {"desde": "E3100000001", "hasta": "E3100000050"},
                {"desde": "E3200000001", "hasta": "E3200000050"},
            ]
        }
        factory = APIRequestFactory()
        request = factory.post("/api/v1/secuencias/", data, format="json")
        force_authenticate(request, user=usuario)

        from sequences.views import onboarding as onboarding_view
        response = onboarding_view(request)
        self.assertEqual(response.status_code, 201)

        sec31 = Secuencial.objects.get(empresa=self.empresa, tipo_ecf=31)
        sec32 = Secuencial.objects.get(empresa=self.empresa, tipo_ecf=32)
        self.assertEqual(sec31.minimo_asignado, 1)
        self.assertEqual(sec31.maximo_asignado, 50)
        self.assertEqual(sec31.ultimo_numero, 0)
        self.assertEqual(sec32.minimo_asignado, 1)
        self.assertEqual(sec32.maximo_asignado, 50)

    def test_volumen_excede_limite_rechazado(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from users.models import Usuario

        usuario = Usuario.objects.create_user(
            email="admin@test.com", password="Test123456",
            nombre="Admin", apellido="Test",
            empresa=self.empresa, rol=Usuario.ROL_SUPERADMIN,
        )

        data = {
            "secuencias": [
                {"desde": "E3100000001", "hasta": "E3100010000"},
            ]
        }
        factory = APIRequestFactory()
        request = factory.post("/api/v1/secuencias/", data, format="json")
        force_authenticate(request, user=usuario)

        from sequences.views import onboarding as onboarding_view
        response = onboarding_view(request)
        self.assertEqual(response.status_code, 403)
        self.assertIn("excede", str(response.data))

    def test_secuencia_item_formato_invalido(self):
        from sequences.serializers import SecuenciaItemSerializer
        serializer = SecuenciaItemSerializer(data={
            "desde": "INVALIDO", "hasta": "E3100000050"
        })
        self.assertFalse(serializer.is_valid())

    def test_secuencia_item_desde_mayor_hasta_error(self):
        from sequences.serializers import SecuenciaItemSerializer
        serializer = SecuenciaItemSerializer(data={
            "desde": "E3100000050", "hasta": "E3100000001"
        })
        self.assertFalse(serializer.is_valid())

    def test_secuencia_item_tipos_distintos_error(self):
        from sequences.serializers import SecuenciaItemSerializer
        serializer = SecuenciaItemSerializer(data={
            "desde": "E3100000001", "hasta": "E3200000050"
        })
        self.assertFalse(serializer.is_valid())

    def test_secuencia_item_valido(self):
        from sequences.serializers import SecuenciaItemSerializer
        serializer = SecuenciaItemSerializer(data={
            "desde": "E3100000001", "hasta": "E3100000050"
        })
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["volumen"], 50)
        self.assertEqual(serializer.validated_data["tipo_ecf"], 31)
