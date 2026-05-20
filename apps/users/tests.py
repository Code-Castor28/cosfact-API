from rest_framework import status
from rest_framework.test import APITestCase
from users.models import Usuario
from empresas.models import Empresa
from api_keys.models import ApiKey


class UsersAdminApiKeyAuthTests(APITestCase):
    def setUp(self):
        self.superadmin = Usuario.objects.create_superuser(
            email="admin@example.com",
            password="Admin123456",
            nombre="Super",
            apellido="Admin",
        )
        self.empresa = Empresa.objects.create(
            rnc="131793916",
            razon_social="Empresa de Prueba SRL",
            nombre_comercial="amigostodos",
        )
        key, self.api_token = ApiKey.crear(
            empresa=self.empresa,
            nombre="POS Test",
            creado_por=self.superadmin,
            scopes=["comprobantes:crear"],
            allowed_ips=[],
            rate_limit_cantidad=100,
            rate_limit_ventana=ApiKey.VENTANA_HORA,
        )
        self.base_url = "/api/v1/users/"

    def test_api_key_gets_200_empty_on_users_list(self):
        resp = self.client.get(
            self.base_url,
            HTTP_AUTHORIZATION=f"Api-Key {self.api_token}",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"], [])

    def test_api_key_gets_403_on_users_create(self):
        resp = self.client.post(
            self.base_url,
            {"email": "test@test.com", "password": "Test123456"},
            format="json",
            HTTP_AUTHORIZATION=f"Api-Key {self.api_token}",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_key_gets_403_on_users_me(self):
        resp = self.client.get(
            f"{self.base_url}me/",
            HTTP_AUTHORIZATION=f"Api-Key {self.api_token}",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
