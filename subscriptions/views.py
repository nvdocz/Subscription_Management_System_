from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdminOrStaff
from config.pagination import StandardPagination

from . import services
from .models import Subscription, activate_due_subscriptions, close_expired_subscriptions
from .serializers import SubscriptionDetailSerializer, SubscriptionListSerializer

LIST_LINE_AMOUNT = ExpressionWrapper(
    F('lines__quantity') * F('lines__unit_price'), output_field=DecimalField(max_digits=14, decimal_places=2)
)

ORDERINGS = {
    'created': '-created_at',
    'start': '-start_date',
    'next_billing': 'next_billing_date',
    'expiry': 'expiry_date',
    'number': 'number',
}


class SubscriptionViewSet(viewsets.ModelViewSet):
    pagination_class = StandardPagination

    def get_serializer_class(self):
        return SubscriptionListSerializer if self.action == 'list' else SubscriptionDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Subscription.objects.select_related('customer', 'plan__product')
        if self.action == 'list':
            qs = qs.annotate(cycle_total=Sum(LIST_LINE_AMOUNT))
        if self.action != 'list':
            qs = qs.prefetch_related('lines__product', 'lines__variant', 'events__actor')
        if user.role == User.Role.CUSTOMER:
            qs = qs.filter(customer=user).exclude(status=Subscription.Status.DRAFT)

        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status__in=params['status'].split(','))
        if params.get('customer'):
            qs = qs.filter(customer_id=params['customer'])
        if params.get('plan'):
            qs = qs.filter(plan_id=params['plan'])
        if params.get('q'):
            term = params['q'].strip()
            qs = qs.filter(
                Q(number__icontains=term) | Q(customer__username__icontains=term) | Q(plan__name__icontains=term)
            )
        return qs.order_by(ORDERINGS.get(params.get('ordering'), '-created_at'), '-id')

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'do'):
            return [IsAuthenticated()]
        return [IsAdminOrStaff()]

    def list(self, request, *args, **kwargs):
        activate_due_subscriptions()
        close_expired_subscriptions()
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status=Subscription.Status.DRAFT)

    def perform_update(self, serializer):
        if serializer.instance.status not in (Subscription.Status.DRAFT, Subscription.Status.QUOTATION):
            raise ValidationError('Only draft or quotation-stage subscriptions can be edited.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != Subscription.Status.DRAFT:
            raise ValidationError('Only draft subscriptions can be deleted. Close it instead.')
        instance.delete()

    @action(detail=True, methods=['post'], url_path=r'do/(?P<action_name>[a-z_]+)')
    def do(self, request, pk=None, action_name=None):
        subscription = self.get_object()
        services.perform(subscription, action_name, request.user)
        subscription.refresh_from_db()
        return Response(SubscriptionDetailSerializer(subscription, context=self.get_serializer_context()).data)
