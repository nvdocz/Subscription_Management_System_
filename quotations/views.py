from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdminOrStaff

from .models import Quotation, QuotationTemplate
from .serializers import QuotationSerializer, QuotationTemplateSerializer
from .services import convert_quotation


class QuotationViewSet(viewsets.ModelViewSet):
    serializer_class = QuotationSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Quotation.objects.select_related('customer', 'plan', 'subscription').prefetch_related('items')
        if user.role == User.Role.CUSTOMER:
            qs = qs.filter(customer=user).exclude(status=Quotation.Status.DRAFT)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'accept', 'reject'):
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdminOrStaff]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.status != Quotation.Status.DRAFT:
            raise ValidationError('Only draft quotations can be edited.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != Quotation.Status.DRAFT:
            raise ValidationError('Only draft quotations can be deleted.')
        instance.delete()

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        quotation = self.get_object()
        if quotation.status != Quotation.Status.DRAFT:
            raise ValidationError('Only draft quotations can be sent.')
        quotation.status = Quotation.Status.SENT
        quotation.save(update_fields=['status'])
        return Response(self.get_serializer(quotation).data)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        quotation = self.get_object()
        if request.user.role == User.Role.CUSTOMER and quotation.customer_id != request.user.id:
            raise PermissionDenied('You can only respond to your own quotations.')
        quotation.refresh_status()
        if quotation.status != Quotation.Status.SENT:
            raise ValidationError('Only sent quotations can be accepted.')
        quotation.status = Quotation.Status.ACCEPTED
        quotation.save(update_fields=['status'])
        if quotation.plan_id and quotation.created_by_id == quotation.customer_id:
            convert_quotation(quotation, request.user)
        return Response(self.get_serializer(quotation).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        quotation = self.get_object()
        if request.user.role == User.Role.CUSTOMER and quotation.customer_id != request.user.id:
            raise PermissionDenied('You can only respond to your own quotations.')
        quotation.refresh_status()
        if quotation.status != Quotation.Status.SENT:
            raise ValidationError('Only sent quotations can be rejected.')
        quotation.status = Quotation.Status.REJECTED
        quotation.save(update_fields=['status'])
        return Response(self.get_serializer(quotation).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrStaff])
    def convert(self, request, pk=None):
        quotation = self.get_object()
        convert_quotation(quotation, request.user)
        return Response(self.get_serializer(quotation).data)


class QuotationTemplateViewSet(viewsets.ModelViewSet):
    queryset = QuotationTemplate.objects.prefetch_related('items')
    serializer_class = QuotationTemplateSerializer
    permission_classes = [IsAdminOrStaff]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
