from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdmin, IsCustomer
from pricing.models import tax_rate_for
from quotations.models import Quotation, QuotationItem
from subscriptions.models import Subscription

from .models import SubscriptionPlan
from .serializers import CatalogPlanSerializer, SubscriptionPlanSerializer


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.select_related('product').all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAdmin]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.subscriptions.exists():
            raise ValidationError('This plan has subscriptions. Switch it off to stop new sign-ups instead of deleting it.')
        instance.delete()

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        plan = self.get_object()
        plan.is_active = False
        plan.save(update_fields=['is_active'])
        return Response(self.get_serializer(plan).data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        plan = self.get_object()
        plan.is_active = True
        plan.save(update_fields=['is_active'])
        return Response(self.get_serializer(plan).data)


class CatalogPlanListView(generics.ListAPIView):
    serializer_class = CatalogPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        today = timezone.localdate()
        return (
            SubscriptionPlan.objects.filter(is_active=True, product__is_archived=False, start_date__lte=today)
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
            .select_related('product')
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        if user.role == User.Role.CUSTOMER:
            context['active_by_product'] = customer_active_plans(user)
            context['requested_plan_ids'] = set(
                open_quotations(user).filter(plan__isnull=False).values_list('plan_id', flat=True)
            )
        return context


def open_quotations(user):
    pending = Q(status__in=[Quotation.Status.DRAFT, Quotation.Status.SENT])
    accepted_not_converted = Q(status=Quotation.Status.ACCEPTED, subscription__isnull=True)
    return Quotation.objects.filter(pending | accepted_not_converted, customer=user)


def customer_active_plans(user):
    active = {}
    for subscription in Subscription.objects.filter(customer=user, status=Subscription.Status.ACTIVE).select_related('plan'):
        best = active.get(subscription.plan.product_id)
        if best is None or subscription.plan.price > best.price:
            active[subscription.plan.product_id] = subscription.plan
    return active


class PlanRequestView(APIView):
    permission_classes = [IsCustomer]

    def post(self, request, pk):
        plan = get_object_or_404(
            SubscriptionPlan, pk=pk, is_active=True, product__is_archived=False, start_date__lte=timezone.localdate()
        )
        if plan.end_date and plan.end_date < timezone.localdate():
            return Response({'detail': 'This plan is no longer available.'}, status=status.HTTP_400_BAD_REQUEST)
        current = customer_active_plans(request.user).get(plan.product_id)
        if current is not None and current.pk == plan.pk:
            return Response({'detail': 'You are already on this plan.'}, status=status.HTTP_400_BAD_REQUEST)
        if current is not None and plan.price <= current.price:
            return Response(
                {'detail': 'To move to a lower plan, please contact our team.'}, status=status.HTTP_400_BAD_REQUEST
            )
        if open_quotations(request.user).filter(plan=plan).exists():
            return Response(
                {'detail': 'You already have an open quotation for this plan.'}, status=status.HTTP_400_BAD_REQUEST
            )

        kind = 'Upgrade' if current else 'New subscription'
        quotation = Quotation.objects.create(
            customer=request.user,
            created_by=request.user,
            plan=plan,
            status=Quotation.Status.SENT,
            notes=f'{kind} requested from Browse Plans' + (f' (from {current.name})' if current else ''),
        )
        QuotationItem.objects.create(
            quotation=quotation, product=plan.product, quantity=plan.min_quantity, unit_price=plan.price, tax_rate=tax_rate_for(plan.product)
        )
        return Response({'quotation': quotation.pk, 'detail': 'Request sent. Review it under My Quotations.'}, status=status.HTTP_201_CREATED)
