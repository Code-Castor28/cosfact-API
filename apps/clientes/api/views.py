from rest_framework import viewsets, permissions
from clientes.models import Cliente
from clientes.serializers import ClienteSerializer
from empresas.models import Empresa


class ClienteViewSet(viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'rnc_cedula'

    def _get_empresa(self):
        user = self.request.user
        if isinstance(user, Empresa):
            return user
        return user.empresa

    def get_queryset(self):
        return Cliente.objects.filter(empresa=self._get_empresa())

    def perform_create(self, serializer):
        serializer.save(empresa=self._get_empresa())

    def perform_update(self, serializer):
        serializer.save(empresa=self._get_empresa())
