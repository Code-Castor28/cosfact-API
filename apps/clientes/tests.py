import hashlib
import secrets
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model

from empresas.models import Empresa
from api_keys.models import ApiKey
from clientes.models import Cliente

Usuario = get_user_model()


class ClienteModelTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )

    def test_cliente_creado_con_datos_validos(self):
        cliente = Cliente.objects.create(
            empresa=self.empresa,
            rnc_cedula="00123456789",
            razon_social="Juan Pérez",
        )
        self.assertEqual(cliente.rnc_cedula, "00123456789")
        self.assertEqual(cliente.razon_social, "Juan Pérez")
        self.assertEqual(cliente.empresa, self.empresa)

    def test_rnc_cedula_no_numerico_lanza_error(self):
        with self.assertRaises(Exception):
            Cliente.objects.create(
                empresa=self.empresa,
                rnc_cedula="ABCD1234567",
                razon_social="Cliente inválido",
            )

    def test_rnc_cedula_longitud_invalida_lanza_error(self):
        with self.assertRaises(Exception):
            Cliente.objects.create(
                empresa=self.empresa,
                rnc_cedula="123",
                razon_social="Cliente inválido",
            )

    def test_rnc_cedula_9_digitos_persona_juridica(self):
        cliente = Cliente.objects.create(
            empresa=self.empresa,
            rnc_cedula="123456789",
            razon_social="Empresa Jurídica",
        )
        self.assertEqual(cliente.rnc_cedula, "123456789")

    def test_rnc_cedula_11_digitos_persona_fisica(self):
        cliente = Cliente.objects.create(
            empresa=self.empresa,
            rnc_cedula="00123456789",
            razon_social="Persona Física",
        )
        self.assertEqual(cliente.rnc_cedula, "00123456789")

    def test_rnc_cedula_duplicado_misma_empresa_lanza_error(self):
        Cliente.objects.create(
            empresa=self.empresa,
            rnc_cedula="00123456789",
            razon_social="Cliente A",
        )
        with self.assertRaises(Exception):
            Cliente.objects.create(
                empresa=self.empresa,
                rnc_cedula="00123456789",
                razon_social="Cliente B",
            )

    def test_mismo_rnc_distinta_empresa_ok(self):
        empresa2 = Empresa.objects.create(
            rnc="98765432101",
            razon_social="Empresa 2",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )
        Cliente.objects.create(
            empresa=self.empresa,
            rnc_cedula="00123456789",
            razon_social="Cliente A",
        )
        cliente2 = Cliente.objects.create(
            empresa=empresa2,
            rnc_cedula="00123456789",
            razon_social="Cliente B",
        )
        self.assertEqual(cliente2.rnc_cedula, "00123456789")


class ClienteAPITest(APITestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            rnc="12345678901",
            razon_social="Empresa Test",
            ambiente=Empresa.AMBIENTE_TEST,
            estado=Empresa.ESTADO_ACTIVA,
        )
        self.usuario = Usuario.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            nombre="Admin",
            rol=Usuario.ROL_SUPERADMIN,
        )
        _, self.token = ApiKey.crear(
            empresa=self.empresa,
            nombre="Test Key",
            creado_por=self.usuario,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {self.token}")

    def test_crear_cliente_201(self):
        data = {
            "rnc_cedula": "00123456789",
            "razon_social": "Juan Pérez",
            "email": "juan@example.com",
            "telefono": "8095550100",
        }
        response = self.client.post("/api/v1/clientes/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["rnc_cedula"], "00123456789")

    def test_crear_cliente_sin_auth_401(self):
        self.client.credentials()
        data = {
            "rnc_cedula": "00123456789",
            "razon_social": "Juan Pérez",
        }
        response = self.client.post("/api/v1/clientes/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_listar_clientes_filtro_empresa(self):
        Cliente.objects.create(
            empresa=self.empresa,
            rnc_cedula="00123456789",
            razon_social="Cliente A",
        )
        response = self.client.get("/api/v1/clientes/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["razon_social"], "Cliente A")

    def test_rnc_cedula_invalido_400(self):
        data = {
            "rnc_cedula": "ABC",
            "razon_social": "Cliente inválido",
        }
        response = self.client.post("/api/v1/clientes/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_actualizar_cliente_200(self):
        cliente = Cliente.objects.create(
            empresa=self.empresa,
            rnc_cedula="00123456789",
            razon_social="Nombre Viejo",
        )
        data = {"razon_social": "Nombre Nuevo"}
        response = self.client.patch(
            f"/api/v1/clientes/00123456789/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["razon_social"], "Nombre Nuevo")

    def test_eliminar_cliente_204(self):
        Cliente.objects.create(
            empresa=self.empresa,
            rnc_cedula="00123456789",
            razon_social="Cliente a eliminar",
        )
        response = self.client.delete("/api/v1/clientes/00123456789/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
