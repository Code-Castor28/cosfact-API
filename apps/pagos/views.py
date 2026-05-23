from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from typing import Type

from .models import Pago, HistorialPago
from .serializers import (
    PagoSerializer,
    PagoDetailSerializer,
    PagoUpdateSerializer,
    HistorialPagoSerializer,
)
from .permissions import IsSuperAdmin, IsAdminEmpresaOrSuperAdmin
from subscriptions.models import Suscripcion, PaqueteComprobantes


class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.select_related(
        "empresa", "plan", "suscripcion", "confirmado_por"
    ).all()
    permission_classes = [IsSuperAdmin]

    def get_serializer_class(self) -> Type:
        if self.action == 'retrieve':
            return PagoDetailSerializer
        if self.action == 'actualizar_confirmacion':
            return PagoUpdateSerializer
        if self.action == 'historial':
            return HistorialPagoSerializer
        return PagoSerializer

    def get_queryset(self):
        """
        Por defecto, retorna solo pagos PENDIENTES.
        Query param: ?estado=CONFIRMADO para filtrar otros.
        """
        queryset = super().get_queryset()
        estado = self.request.query_params.get('estado')

        if not estado:
            # Por defecto: solo PENDIENTES
            queryset = queryset.filter(estado=Pago.ESTADO_PENDIENTE)
        else:
            queryset = queryset.filter(estado=estado)

        return queryset

    def create(self, request, *args, **kwargs):
        """
        POST deshabilitado para usuario normal.
        Los pagos se generan automáticamente.
        Solo admin puede crear manualmente para casos especiales (adelantos, cambios de plan).
        """
        return Response(
            {
                "error": "No se puede crear pagos directamente. "
                         "Los pagos se generan automáticamente. "
                         "Contacta a administración para casos especiales."
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def perform_create(self, serializer):
        """
        [DEPRECATED] - create() está deshabilitado
        """
        empresa = serializer.validated_data['empresa']
        suscripcion = serializer.validated_data['suscripcion']

        if not empresa.activa:
            raise ValidationError({"empresa": "La empresa no está activa."})

        if not suscripcion:
            raise ValidationError(
                {"suscripcion": "La empresa debe tener una suscripción."})

        if suscripcion.estado not in [Suscripcion.ESTADO_ACTIVA, Suscripcion.ESTADO_VENCIDA, Suscripcion.ESTADO_SUSPENDIDA]:
            raise ValidationError(
                {"suscripcion": "La suscripción no está en un estado válido para crear pago."})

        serializer.save()

    @action(detail=True, methods=['patch'])
    def actualizar_confirmacion(self, request, pk=None):
        """
        PATCH /api/v1/pagos/{id}/actualizar_confirmacion/

        Permite actualizar SOLO:
        - metodo_pago
        - referencia
        - observaciones

        Al completar validación, confirma el pago automáticamente.
        Valida: referencia requerida si metodo_pago != EFECTIVO
        """
        pago = self.get_object()

        # Validar estado
        if pago.estado != Pago.ESTADO_PENDIENTE:
            return Response(
                {
                    "error": f"No se puede actualizar pago en estado {pago.estado}. "
                    "Solo PENDIENTE."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Usar serializer de actualización
        serializer = self.get_serializer(pago, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Validar referencia si no es EFECTIVO
        metodo_pago = serializer.validated_data.get(
            'metodo_pago', pago.metodo_pago)
        referencia = serializer.validated_data.get(
            'referencia', pago.referencia or '').strip()

        if metodo_pago and metodo_pago != Pago.METODO_EFECTIVO:
            if not referencia:
                return Response(
                    {
                        "error": f"Referencia requerida para pagos por {metodo_pago}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Actualizar campos
        pago.metodo_pago = metodo_pago
        pago.referencia = serializer.validated_data.get(
            'referencia', pago.referencia)
        pago.observaciones = serializer.validated_data.get(
            'observaciones', pago.observaciones)
        pago.save()

        # Confirmar pago automáticamente
        return self._confirmar_pago_internamente(pago, request)

    def _confirmar_pago_internamente(self, pago, request):
        """
        Lógica interna de confirmación de pago.
        Reutilizable por actualizar_confirmacion y confirmar.
        """
        if pago.estado != Pago.ESTADO_PENDIENTE:
            return Response(
                {"error": "Solo se pueden confirmar pagos en estado PENDIENTE."},
                status=status.HTTP_400_BAD_REQUEST
            )

        fecha_pago = pago.fecha_pago
        fecha_corte = pago.fecha_corte
        dia_actual = fecha_pago.day

        if dia_actual <= fecha_corte:
            periodo_mes = fecha_pago.month
            periodo_ano = fecha_pago.year
        else:
            siguiente = fecha_pago + relativedelta(months=1)
            periodo_mes = siguiente.month
            periodo_ano = siguiente.year

        existe_historial = HistorialPago.objects.filter(
            empresa=pago.empresa,
            periodo_mes=periodo_mes,
            periodo_ano=periodo_ano,
        ).exists()

        if existe_historial:
            return Response(
                {"error": f"Ya existe un pago confirmado para el período {periodo_mes}/{periodo_ano}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            pago.estado = Pago.ESTADO_CONFIRMADO
            pago.confirmado_por = request.user
            pago.fecha_confirmacion = timezone.now()
            pago.save()

            suscripcion = pago.suscripcion
            if periodo_mes == 12:
                fecha_inicio = datetime(periodo_ano, 1, 1).date()
            else:
                fecha_inicio = datetime(periodo_ano, periodo_mes, 1).date()

            if periodo_mes == 12:
                fecha_fin = datetime(periodo_ano + 1, 1, 1).date()
            else:
                fecha_fin = datetime(periodo_ano, periodo_mes + 1, 1).date()
            fecha_fin = fecha_fin - relativedelta(days=1)

            suscripcion.fecha_inicio = fecha_inicio
            suscripcion.fecha_renovacion = fecha_fin
            suscripcion.estado = Suscripcion.ESTADO_ACTIVA
            suscripcion.plan = pago.plan
            suscripcion.save()

            fecha_vencimiento = None
            if suscripcion.ciclo in [Suscripcion.CICLO_MENSUAL, Suscripcion.CICLO_ANUAL]:
                fecha_vencimiento = timezone.make_aware(
                    datetime.combine(fecha_fin, datetime.min.time()))

            paquete = PaqueteComprobantes.objects.create(
                empresa=pago.empresa,
                suscripcion=suscripcion,
                plan=pago.plan,
                total_comprobantes=pago.plan.limite_comprobantes,
                comprobantes_usados=0,
                estado=PaqueteComprobantes.ESTADO_ACTIVO,
                origen=PaqueteComprobantes.ORIGEN_SUSCRIPCION,
                fecha_vencimiento=fecha_vencimiento,
            )

            historial = HistorialPago.objects.create(
                empresa=pago.empresa,
                suscripcion=suscripcion,
                plan=pago.plan,
                pago=pago,
                paquete=paquete,
                periodo_mes=periodo_mes,
                periodo_ano=periodo_ano,
                monto_pagado=pago.monto,
                comprobantes_asignados=pago.plan.limite_comprobantes,
            )

        serializer = PagoDetailSerializer(pago)
        return Response({
            "pago": serializer.data,
            "suscripcion": {
                "id": str(suscripcion.id),
                "estado": suscripcion.estado,
                "fecha_inicio": str(suscripcion.fecha_inicio),
                "fecha_renovacion": str(suscripcion.fecha_renovacion),
            },
            "paquete": {
                "id": str(paquete.id),
                "total_comprobantes": paquete.total_comprobantes,
                "estado": paquete.estado,
            },
            "historial": HistorialPagoSerializer(historial).data,
        })

    def destroy(self, request, *args, **kwargs):
        """
        Solo se pueden eliminar pagos en estado PENDIENTE.
        """
        instance = self.get_object()
        if instance.estado != Pago.ESTADO_PENDIENTE:
            return Response(
                {"error": "Solo se pueden eliminar pagos en estado PENDIENTE."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        """
        [DEPRECATED - usar actualizar_confirmacion en su lugar]

        POST /api/v1/pagos/{id}/confirmar/

        Se mantiene por compatibilidad hacia atrás.
        En futuro será removido a favor de actualizar_confirmacion.
        """
        return self._confirmar_pago_internamente(self.get_object(), request)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        pago = self.get_object()

        if pago.estado != Pago.ESTADO_PENDIENTE:
            return Response(
                {"error": "Solo se pueden rechazar pagos en estado PENDIENTE."},
                status=status.HTTP_400_BAD_REQUEST
            )

        pago.estado = Pago.ESTADO_RECHAZADO
        pago.save()

        serializer = PagoDetailSerializer(pago)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='historial')
    def historial(self, request):
        qs = HistorialPago.objects.select_related(
            "empresa", "plan", "suscripcion", "pago", "paquete"
        ).all().order_by('-periodo_ano', '-periodo_mes')

        empresa_id = request.query_params.get('empresa')
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)

        page = self.paginate_queryset(qs)
        serializer = HistorialPagoSerializer(
            page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)
