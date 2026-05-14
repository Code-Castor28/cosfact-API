from rest_framework import status
from rest_framework.test import APITestCase
from users.models import Usuario
from empresas.models import Empresa
from .models import ApiKey


class ApiKeyApiTests(APITestCase):
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
        self.client.force_authenticate(user=self.superadmin)
        self.base_url = "/api/v1/api-keys/"

    def test_create_returns_token_only_once(self):
        payload = {
            "empresa": str(self.empresa.id),
            "nombre": "POS Sucursal Norte",
            "scopes": ["comprobantes:crear"],
            "allowed_ips": [],
            "rate_limit_cantidad": 100,
            "rate_limit_ventana": "HOUR",
            "expira_at": None,
            "activa": True,
        }

        create_resp = self.client.post(self.base_url, payload, format="json")
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", create_resp.data)
        key_id = create_resp.data["id"]

        detail_resp = self.client.get(f"{self.base_url}{key_id}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertNotIn("token", detail_resp.data)

        list_resp = self.client.get(self.base_url)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        if list_resp.data.get("results"):
            self.assertNotIn("token", list_resp.data["results"][0])

    def test_invalid_scope_is_rejected(self):
        payload = {
            "empresa": str(self.empresa.id),
            "nombre": "POS Sucursal Norte",
            "scopes": ["invalido:scope"],
        }
        resp = self.client.post(self.base_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rotate_creates_new_key_and_revokes_old(self):
        key, _token = ApiKey.crear(
            empresa=self.empresa,
            nombre="POS Sucursal Norte",
            creado_por=self.superadmin,
            scopes=["comprobantes:crear"],
            allowed_ips=[],
            rate_limit_cantidad=100,
            rate_limit_ventana=ApiKey.VENTANA_HORA,
        )

        resp = self.client.post(
            f"{self.base_url}{key.id}/rotar/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", resp.data)
        self.assertIn("key_revocada_id", resp.data)

        key.refresh_from_db()
        self.assertFalse(key.activa)
