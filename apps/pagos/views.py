from datetime import datetime
from decimal import Decimal
from calendar import isleap
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from typing import Type

from .models import Pago, HistorialPago
from .serializers import (
    PagoSerializer,
    PagoCreateSerializer,
    PagoDetailSerializer,
    PagoUpdateSerializer,
    HistorialPagoSerializer,
)
from .permissions import IsSuperAdmin
from .pdf import generar_pdf_a4, generar_pdf_80mm
from subscriptions.models import Suscripcion, PaqueteComprobantes


class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.select_related(
        "empresa", "plan", "suscripcion", "confirmado_por"
    ).all()
    permission_classes = [IsSuperAdmin]

    def get_serializer_class(self) -> Type:
        if self.action == 'create':
            return PagoCreateSerializer
        if self.action == 'retrieve':
            return PagoDetailSerializer
        if self.action == 'actualizar_confirmacion':
            return PagoUpdateSerializer
        if self.action == 'historial':
            return HistorialPagoSerializer
        return PagoSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            estado = self.request.query_params.get('estado')
            if not estado:
                queryset = queryset.filter(estado=Pago.ESTADO_PENDIENTE)
            else:
                queryset = queryset.filter(estado=estado)
        return queryset

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
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

        monto = serializer.validated_data.get('monto')

        if monto is None:
            es_primer_pago = not Pago.objects.filter(
                suscripcion=suscripcion,
                estado=Pago.ESTADO_CONFIRMADO,
            ).exists()
            if es_primer_pago and suscripcion.fecha_corte:
                monto = self._calcular_monto_prorrateado(suscripcion)
                serializer.save(monto=monto)
                return

        serializer.save()

    def _calcular_monto_prorrateado(self, suscripcion):
        fecha_inicio = suscripcion.fecha_inicio
        corte = suscripcion.fecha_corte
        plan = suscripcion.plan

        if fecha_inicio.day <= corte:
            primer_corte = datetime(fecha_inicio.year, fecha_inicio.month, corte).date()
        else:
            mes_sig = fecha_inicio + relativedelta(months=1)
            primer_corte = datetime(mes_sig.year, mes_sig.month, corte).date()

        if fecha_inicio.day >= corte:
            corte_anterior = datetime(fecha_inicio.year, fecha_inicio.month, corte).date()
        else:
            mes_ant = fecha_inicio - relativedelta(months=1)
            corte_anterior = datetime(mes_ant.year, mes_ant.month, corte).date()

        dias_periodo = (primer_corte - corte_anterior).days
        dias_usados = (primer_corte - fecha_inicio).days

        if suscripcion.ciclo == Suscripcion.CICLO_ANUAL:
            year = fecha_inicio.year
            dias_anio = 366 if isleap(year) else 365
            return (plan.precio_anual * Decimal(dias_usados) / Decimal(dias_anio)).quantize(Decimal('0.01'))

        return (plan.precio_mensual * Decimal(dias_usados) / Decimal(dias_periodo)).quantize(Decimal('0.01'))

    @action(detail=True, methods=['patch'])
    def actualizar_confirmacion(self, request, pk=None):
        pago = self.get_object()

        if pago.estado != Pago.ESTADO_PENDIENTE:
            return Response(
                {
                    "error": f"No se puede actualizar pago en estado {pago.estado}. "
                    "Solo PENDIENTE."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(pago, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

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

        pago.metodo_pago = metodo_pago
        pago.referencia = serializer.validated_data.get(
            'referencia', pago.referencia)
        pago.observaciones = serializer.validated_data.get(
            'observaciones', pago.observaciones)
        pago.save()

        return self._confirmar_pago_internamente(pago, request)

    def _confirmar_pago_internamente(self, pago, request):
        if pago.estado != Pago.ESTADO_PENDIENTE:
            return Response(
                {"error": "Solo se pueden confirmar pagos en estado PENDIENTE."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            pago.estado = Pago.ESTADO_CONFIRMADO
            pago.confirmado_por = request.user
            pago.fecha_confirmacion = timezone.now()
            pago.save()

            suscripcion = pago.suscripcion

            if pago.tipo_pago == Pago.TIPO_RENOVACION:
                nueva_fecha_inicio = suscripcion.fecha_renovacion
                periodo_mes = nueva_fecha_inicio.month
                periodo_ano = nueva_fecha_inicio.year

                if suscripcion.ciclo == Suscripcion.CICLO_ANUAL:
                    nueva_fecha_renovacion = nueva_fecha_inicio + relativedelta(years=1)
                else:
                    nueva_fecha_renovacion = nueva_fecha_inicio + relativedelta(months=1)

                existe_historial = HistorialPago.objects.filter(
                    empresa=pago.empresa,
                    suscripcion=suscripcion,
                    periodo_mes=periodo_mes,
                    periodo_ano=periodo_ano,
                    pago__tipo_pago=Pago.TIPO_RENOVACION,
                ).exists()

                if existe_historial:
                    return Response(
                        {"error": f"Ya existe un pago confirmado para el período {periodo_mes}/{periodo_ano}."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                actualizadas = Suscripcion.objects.filter(
                    id=suscripcion.id,
                    fecha_renovacion=suscripcion.fecha_renovacion,
                ).update(
                    fecha_inicio=nueva_fecha_inicio,
                    fecha_renovacion=nueva_fecha_renovacion,
                    estado=Suscripcion.ESTADO_ACTIVA,
                    plan=pago.plan,
                )

                if actualizadas == 0:
                    return Response(
                        {"error": "La suscripción fue modificada por otro proceso."},
                        status=status.HTTP_409_CONFLICT
                    )

                suscripcion.refresh_from_db()

                fecha_vencimiento = timezone.make_aware(
                    datetime.combine(nueva_fecha_renovacion, datetime.min.time())
                )

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

            else:
                paquete = PaqueteComprobantes.objects.create(
                    empresa=pago.empresa,
                    suscripcion=suscripcion,
                    plan=pago.plan,
                    total_comprobantes=pago.plan.limite_comprobantes,
                    comprobantes_usados=0,
                    estado=PaqueteComprobantes.ESTADO_ACTIVO,
                    origen=PaqueteComprobantes.ORIGEN_ADICIONAL,
                    fecha_vencimiento=None,
                )

                ahora = timezone.now()
                historial = HistorialPago.objects.create(
                    empresa=pago.empresa,
                    suscripcion=suscripcion,
                    plan=pago.plan,
                    pago=pago,
                    paquete=paquete,
                    periodo_mes=ahora.month,
                    periodo_ano=ahora.year,
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
        instance = self.get_object()
        if instance.estado != Pago.ESTADO_PENDIENTE:
            return Response(
                {"error": "Solo se pueden eliminar pagos en estado PENDIENTE."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

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

    @action(detail=True, methods=['get'], url_path='pdf/a4')
    def pdf_a4(self, request, pk=None):
        pago = self.get_object()
        pdf_buffer = generar_pdf_a4(pago)
        return FileResponse(
            pdf_buffer,
            content_type='application/pdf',
            as_attachment=True,
            filename=f"comprobante-{pago.id}-a4.pdf",
        )

    @action(detail=True, methods=['get'], url_path='pdf/80mm')
    def pdf_80mm(self, request, pk=None):
        pago = self.get_object()
        pdf_buffer = generar_pdf_80mm(pago)
        return FileResponse(
            pdf_buffer,
            content_type='application/pdf',
            as_attachment=True,
            filename=f"comprobante-{pago.id}-80mm.pdf",
        )
