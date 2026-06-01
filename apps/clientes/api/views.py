from rest_framework import viewsets, permissions
from clientes.models import Cliente
from clientes.serializers import ClienteSerializer


class ClienteViewSet(viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'rnc_cedula'

    def get_queryset(self):
        return Cliente.objects.filter(empresa=self.request.user)

    def perform_create(self, serializer):
        serializer.save(empresa=self.request.user)

    def perform_update(self, serializer):
        serializer.save(empresa=self.request.user)
