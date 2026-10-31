from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdminOrStaff
from config.pagination import StandardPagination

from . import engine
from .models import Invoice, Payment
from .serializers import InvoiceDetailSerializer, InvoiceListSerializer, PaymentSerializer

I = Invoice.Status

INVOICE_ORDERINGS = {
    'issued': '-issue_date',
    'due': 'due_date',
    'amount': '-amount',
    'number': '-number',
}


def allowed_invoice_actions(invoice, user):
    if user.role == User.Role.CUSTOMER:
        if invoice.customer_id == user.id and invoice.status == I.CONFIRMED:
            return ['pay']
        return []
    actions = {
        I.DRAFT: ['confirm', 'cancel'],
        I.CONFIRMED: ['send', 'cancel'] + (['remind'] if invoice.is_overdue else []),
        I.PAID: ['send'],
        I.CANCELLED: [],
    }[I(invoice.status)]
    if invoice.status == I.CONFIRMED and invoice.payments.exists():
        actions.remove('cancel')
    return actions


def date_range(qs, params, field):
    if params.get('from'):
        qs = qs.filter(**{f'{field}__gte': params['from']})
    if params.get('to'):
        qs = qs.filter(**{f'{field}__lte': params['to']})
    return qs


class InvoiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    pagination_class = StandardPagination

    def get_serializer_class(self):
        return InvoiceListSerializer if self.action == 'list' else InvoiceDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Invoice.objects.select_related('customer', 'subscription__plan')
        if self.action != 'list':
            qs = qs.prefetch_related('lines', 'discounts', 'payments__invoice__customer')
        if user.role == User.Role.CUSTOMER:
            qs = qs.filter(customer=user).exclude(status__in=[I.DRAFT, I.CANCELLED])

        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status__in=params['status'].split(','))
        if params.get('overdue') in ('1', 'true'):
            qs = qs.filter(status=I.CONFIRMED, due_date__lt=timezone.localdate())
        if params.get('customer'):
            qs = qs.filter(customer_id=params['customer'])
        if params.get('subscription'):
            qs = qs.filter(subscription_id=params['subscription'])
        if params.get('q'):
            term = params['q'].strip()
            qs = qs.filter(
                Q(number__icontains=term)
                | Q(customer__username__icontains=term)
                | Q(subscription__number__icontains=term)
            )
        qs = date_range(qs, params, 'issue_date')
        return qs.order_by(INVOICE_ORDERINGS.get(params.get('ordering'), '-issue_date'), '-id')

    def get_permissions(self):
        if self.action in ('confirm', 'cancel', 'send', 'remind', 'confirm_drafts'):
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]

    def _respond(self, invoice):
        invoice.refresh_from_db()
        return Response(InvoiceDetailSerializer(invoice, context=self.get_serializer_context()).data)

    def _guard(self, invoice, name):
        if name not in allowed_invoice_actions(invoice, self.request.user):
            raise ValidationError(f'This invoice cannot be {name}ed right now.' if name != 'pay' else 'This invoice cannot be paid.')

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        invoice = self.get_object()
        self._guard(invoice, 'confirm')
        invoice.status = I.CONFIRMED
        invoice.save(update_fields=['status'])
        return self._respond(invoice)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        self._guard(invoice, 'cancel')
        invoice.status = I.CANCELLED
        invoice.save(update_fields=['status'])
        return self._respond(invoice)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        invoice = self.get_object()
        self._guard(invoice, 'send')
        send_mail(
            subject=f'Invoice {invoice.number} from Brightloop Software',
            message=(
                f'Hello {invoice.customer.username},\n\nInvoice {invoice.number} for {invoice.amount} is due on '
                f'{invoice.due_date:%d %b %Y}.\n\nThank you,\nBrightloop Software'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.customer.email],
        )
        invoice.sent_at = timezone.now()
        invoice.save(update_fields=['sent_at'])
        return self._respond(invoice)

    @action(detail=True, methods=['post'])
    def remind(self, request, pk=None):
        invoice = self.get_object()
        self._guard(invoice, 'remind')
        send_mail(
            subject=f'Reminder: invoice {invoice.number} is overdue',
            message=(
                f'Hello {invoice.customer.username},\n\nInvoice {invoice.number} (balance {invoice.balance}) was due on '
                f'{invoice.due_date:%d %b %Y}. Please arrange payment.\n\nBrightloop Software'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.customer.email],
        )
        invoice.last_reminder_at = timezone.now()
        invoice.save(update_fields=['last_reminder_at'])
        return self._respond(invoice)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """Customer self-service payment through the demo gateway: settles the full balance."""
        invoice = self.get_object()
        self._guard(invoice, 'pay')
        Payment.objects.create(
            invoice=invoice,
            amount=invoice.balance,
            method=Payment.Method.CARD,
            note='Paid online (demo gateway)',
            recorded_by=request.user,
        )
        invoice.sync_status()
        return self._respond(invoice)

    @action(detail=False, methods=['post'], url_path='confirm-drafts')
    def confirm_drafts(self, request):
        updated = Invoice.objects.filter(status=I.DRAFT).update(status=I.CONFIRMED)
        return Response({'confirmed': updated})


class PaymentViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Payment.objects.select_related('invoice__customer')
        if self.request.user.role == User.Role.CUSTOMER:
            qs = qs.filter(invoice__customer=self.request.user)
        params = self.request.query_params
        if params.get('method'):
            qs = qs.filter(method=params['method'])
        if params.get('invoice'):
            qs = qs.filter(invoice_id=params['invoice'])
        if params.get('q'):
            term = params['q'].strip()
            qs = qs.filter(Q(invoice__number__icontains=term) | Q(invoice__customer__username__icontains=term))
        qs = date_range(qs, params, 'paid_on')
        return qs.order_by('-paid_on', '-id')

    def get_permissions(self):
        permission = IsAuthenticated if self.action in ('list', 'retrieve') else IsAdminOrStaff
        return [permission()]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class BillingPreviewView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        return Response(engine.preview_billing())


class BillingRunView(APIView):
    permission_classes = [IsAdminOrStaff]

    def post(self, request):
        confirm = bool(request.data.get('confirm', False))
        result = engine.run_billing(actor=request.user, confirm=confirm)
        return Response(result, status=status.HTTP_200_OK)
