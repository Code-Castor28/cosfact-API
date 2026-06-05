from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from api_keys.authentication import ApiKeyAuthentication
from .models import Webhook, WebhookEntrega
from .serializers import WebhookSerializer, WebhookEntregaSerializer


class WebhookViewSet(viewsets.ModelViewSet):
    queryset = Webhook.objects.all()
    serializer_class = WebhookSerializer
    authentication_classes = [ApiKeyAuthentication]

    def _get_empresa(self):
        user = self.request.user
        if hasattr(user, "empresa"):
            return user.empresa
        return user

    def get_queryset(self):
        return Webhook.objects.filter(empresa=self._get_empresa())

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        empresa = self._get_empresa()
        instancia, secret = Webhook.crear(
            empresa=empresa,
            nombre=serializer.validated_data["nombre"],
            url=serializer.validated_data["url"],
            eventos=serializer.validated_data.get("eventos", []),
        )
        data = self.get_serializer(instancia).data
        data["secret"] = secret
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def entregas(self, request, pk=None):
        webhook = self.get_object()
        entregas = WebhookEntrega.objects.filter(webhook=webhook)
        page = self.paginate_queryset(entregas)
        if page is not None:
            serializer = WebhookEntregaSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = WebhookEntregaSerializer(entregas, many=True)
        return Response(serializer.data)
