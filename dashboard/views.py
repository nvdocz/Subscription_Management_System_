from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdmin, IsAdminOrStaff, IsCustomer, IsStaff
from accounts.serializers import UserSerializer
from billing.models import Invoice, Payment
from billing.serializers import InvoiceListSerializer, PaymentSerializer
from plans.models import SubscriptionPlan
from products.models import Product
from quotations.models import Quotation
from subscriptions.models import Subscription, activate_due_subscriptions, close_expired_subscriptions
from subscriptions.serializers import SubscriptionListSerializer

from . import metrics as m

ZERO = m.ZERO


def sync_lifecycle():
    activate_due_subscriptions()
    close_expired_subscriptions()


def recent_subscriptions(request, queryset=None, limit=5):
    queryset = Subscription.objects.all() if queryset is None else queryset
    rows = queryset.select_related('customer', 'plan__product').order_by('-created_at')[:limit]
    return SubscriptionListSerializer(rows, many=True, context={'request': request}).data


def recent_invoices(queryset, limit=5):
    rows = queryset.select_related('customer', 'subscription__plan').order_by('-issue_date', '-id')[:limit]
    return InvoiceListSerializer(rows, many=True).data


class AdminDashboardView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        sync_lifecycle()
        invoices = m.invoice_buckets()
        collection = m.collection_rate()
        month_start = timezone.localdate().replace(day=1)
        mrr = m.current_mrr()
        stats = {
            'total_customers': User.objects.filter(role=User.Role.CUSTOMER).count(),
            'total_staff': User.objects.filter(role=User.Role.STAFF).count(),
            'total_products': Product.objects.filter(is_archived=False).count(),
            'active_subscriptions': Subscription.objects.filter(status=Subscription.Status.ACTIVE).count(),
            'monthly_recurring_revenue': mrr,
            'annual_recurring_revenue': mrr * 12,
            'total_revenue': Payment.objects.aggregate(total=Sum('amount'))['total'] or ZERO,
            'revenue_this_month': Payment.objects.filter(paid_on__gte=month_start).aggregate(total=Sum('amount'))['total'] or ZERO,
            'outstanding_invoices': invoices['outstanding'],
            'overdue_invoices': invoices['overdue'],
            'new_customers_30d': User.objects.filter(
                role=User.Role.CUSTOMER, date_joined__gte=timezone.now() - timedelta(days=30)
            ).count(),
            'churned_30d': m.count_closed_since(30),
            'collection': collection,
            'billing_forecast_30d': m.billing_forecast(30),
        }
        return Response(
            {
                'stats': stats,
                'revenue_by_month': m.revenue_by_month(6),
                'mrr_movement': m.mrr_movement(6),
                'subscription_growth': m.subscription_growth(6),
                'status_breakdown': m.status_breakdown(),
                'invoice_breakdown': m.invoice_status_breakdown(),
                'payment_methods': m.payment_method_mix(),
                'overdue_invoices': m.overdue_rows(),
                'recent_customers': UserSerializer(
                    User.objects.filter(role=User.Role.CUSTOMER).order_by('-date_joined')[:5], many=True
                ).data,
                'recent_subscriptions': recent_subscriptions(request),
                'recent_invoices': recent_invoices(Invoice.objects.exclude(status=Invoice.Status.CANCELLED)),
                'recent_payments': PaymentSerializer(Payment.objects.select_related('invoice__customer')[:5], many=True).data,
            }
        )


class StaffDashboardView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        sync_lifecycle()
        today = timezone.localdate()
        invoices = m.invoice_buckets()
        quotations = Quotation.objects.all()
        awaiting = quotations.filter(status__in=[Quotation.Status.DRAFT, Quotation.Status.SENT])

        activities = []
        for q in quotations.select_related('customer').order_by('-created_at')[:6]:
            activities.append({'type': 'quotation', 'text': f'Quotation #{q.id} for {q.customer.username} is {q.status}', 'at': q.created_at})
        for s in Subscription.objects.select_related('customer', 'plan').order_by('-created_at')[:6]:
            activities.append({'type': 'subscription', 'text': f'{s.number}: {s.customer.username} on {s.plan.name} ({s.status})', 'at': s.created_at})
        for p in Payment.objects.select_related('invoice__customer').order_by('-created_at')[:6]:
            activities.append({'type': 'payment', 'text': f'{p.invoice.customer.username} paid {p.amount} on {p.invoice.number}', 'at': p.created_at})
        activities.sort(key=lambda a: a['at'], reverse=True)

        renewals = (
            Subscription.objects.filter(
                status=Subscription.Status.ACTIVE, next_billing_date__gte=today, next_billing_date__lte=today + timedelta(days=30)
            )
            .select_related('customer', 'plan')
            .order_by('next_billing_date')[:6]
        )
        due_now = Subscription.objects.filter(status=Subscription.Status.ACTIVE, next_billing_date__lte=today).count()

        return Response(
            {
                'stats': {
                    'assigned_customers': quotations.filter(created_by=request.user).values('customer').distinct().count(),
                    'total_quotations': quotations.count(),
                    'pending_quotations': awaiting.count(),
                    'active_subscriptions': Subscription.objects.filter(status=Subscription.Status.ACTIVE).count(),
                    'pending_invoices': invoices['outstanding'],
                    'overdue_invoices': invoices['overdue'],
                    'draft_invoices': Invoice.objects.filter(status=Invoice.Status.DRAFT).count(),
                    'due_for_billing': due_now,
                },
                'recent_activities': activities[:8],
                'quotations_awaiting_action': [
                    {
                        'id': q.id,
                        'customer': q.customer.username,
                        'plan': q.plan.name if q.plan else None,
                        'total': q.total,
                        'status': q.status,
                        'valid_until': q.valid_until,
                    }
                    for q in awaiting.select_related('customer', 'plan').prefetch_related('items').order_by('-created_at')[:6]
                ],
                'recent_subscriptions': recent_subscriptions(request),
                'invoices_awaiting_payment': InvoiceListSerializer(
                    Invoice.objects.filter(status=Invoice.Status.CONFIRMED)
                    .select_related('customer', 'subscription__plan')
                    .order_by('due_date')[:6],
                    many=True,
                ).data,
                'overdue_invoices': m.overdue_rows(5),
                'upcoming_renewals': [
                    {
                        'id': s.id,
                        'number': s.number,
                        'customer': s.customer.username,
                        'plan': s.plan.name,
                        'amount': s.cycle_subtotal,
                        'next_billing_date': s.next_billing_date,
                    }
                    for s in renewals
                ],
            }
        )


class CustomerDashboardView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        sync_lifecycle()
        user = request.user
        today = timezone.localdate()
        invoices = Invoice.objects.filter(customer=user).exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
        buckets = m.invoice_buckets(invoices)
        subscriptions = Subscription.objects.filter(customer=user).select_related('plan__product')
        live = subscriptions.filter(status__in=m.LIVE).order_by('next_billing_date')
        current = live.first()
        available_plans = SubscriptionPlan.objects.filter(
            is_active=True, product__is_archived=False, start_date__lte=today
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=today)).select_related('product')[:6]

        return Response(
            {
                'stats': {
                    'active_subscriptions': subscriptions.filter(status=Subscription.Status.ACTIVE).count(),
                    'total_invoices': invoices.count(),
                    'paid_invoices': invoices.filter(status=Invoice.Status.PAID).count(),
                    'pending_payments': buckets['outstanding'],
                    'overdue_payments': buckets['overdue'],
                },
                'active_subscription': (
                    SubscriptionListSerializer(current, context={'request': request}).data if current else None
                ),
                'next_billing_date': current.next_billing_date if current else None,
                'next_billing_amount': current.cycle_subtotal if current else None,
                'days_to_renewal': (current.expiry_date - today).days if current and current.expiry_date else None,
                'payment_history': PaymentSerializer(
                    Payment.objects.filter(invoice__customer=user).select_related('invoice__customer')[:6], many=True
                ).data,
                'recent_invoices': recent_invoices(invoices),
                'available_plans': [
                    {
                        'id': p.id,
                        'name': p.name,
                        'price': p.price,
                        'billing_frequency': p.billing_frequency,
                        'min_quantity': p.min_quantity,
                        'product': p.product.name,
                    }
                    for p in available_plans
                ],
            }
        )


class ReportsView(APIView):
    """One place for the finance lead: filterable summary of subscriptions, revenue, payments and overdue invoices."""

    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        sync_lifecycle()
        params = request.query_params
        start, end = params.get('from') or None, params.get('to') or None
        plan_id = params.get('plan') or None

        payments = m.in_period(Payment.objects.all(), 'paid_on', start, end)
        invoices = m.in_period(Invoice.objects.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED]), 'issue_date', start, end)
        subscriptions = Subscription.objects.all()
        if plan_id:
            payments = payments.filter(invoice__subscription__plan_id=plan_id)
            invoices = invoices.filter(subscription__plan_id=plan_id)
            subscriptions = subscriptions.filter(plan_id=plan_id)

        revenue = payments.aggregate(total=Sum('amount'))['total'] or ZERO
        invoiced = invoices.aggregate(total=Sum('amount'))['total'] or ZERO
        mrr = m.current_mrr()
        buckets = m.invoice_buckets(invoices.filter(status=Invoice.Status.CONFIRMED) if (start or end or plan_id) else None)

        plan_rows = []
        for plan in SubscriptionPlan.objects.select_related('product'):
            if plan_id and str(plan.id) != str(plan_id):
                continue
            live = Subscription.objects.filter(plan=plan, status=Subscription.Status.ACTIVE)
            lines = m.SubscriptionLine.objects.filter(subscription__in=live)
            plan_rows.append(
                {
                    'plan_id': plan.id,
                    'plan': plan.name,
                    'product': plan.product.name,
                    'active_subscriptions': live.count(),
                    'mrr': m.monthly_value(lines),
                }
            )
        plan_rows.sort(key=lambda r: r['mrr'], reverse=True)

        return Response(
            {
                'filters': {'from': start, 'to': end, 'plan': plan_id},
                'summary': {
                    'active_subscriptions': subscriptions.filter(status=Subscription.Status.ACTIVE).count(),
                    'total_subscriptions': subscriptions.count(),
                    'mrr': mrr,
                    'arr': mrr * 12,
                    'revenue': revenue,
                    'payments_count': payments.count(),
                    'invoiced': invoiced,
                    'collection_rate': round(float(revenue / invoiced * 100), 1) if invoiced else None,
                    'outstanding': buckets['outstanding'],
                    'overdue': buckets['overdue'],
                    'new_subscriptions': m.in_period(subscriptions.exclude(status='draft'), 'start_date', start, end).count(),
                    'closed_subscriptions': m.in_period(
                        subscriptions.filter(status=Subscription.Status.CLOSED), 'end_date', start, end
                    ).count(),
                },
                'revenue_by_month': m.revenue_by_month(12, payments if plan_id else None),
                'mrr_movement': m.mrr_movement(12),
                'subscription_growth': m.subscription_growth(12),
                'status_breakdown': m.status_breakdown(),
                'invoice_breakdown': m.invoice_status_breakdown(),
                'payment_methods': m.payment_method_mix(payments),
                'plans': plan_rows,
                'invoice_aging': m.aging_buckets(),
                'overdue_invoices': m.overdue_rows(15),
                'billing_forecast_30d': m.billing_forecast(30),
            }
        )


class SearchView(APIView):
    """Powers the command palette. Customers only ever see their own records."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        term = request.query_params.get('q', '').strip()
        if len(term) < 2:
            return Response({'results': []})
        user = request.user
        is_staff = user.role != User.Role.CUSTOMER
        results = []

        subs = Subscription.objects.select_related('customer', 'plan').filter(
            Q(number__icontains=term) | Q(customer__username__icontains=term) | Q(plan__name__icontains=term)
        )
        invoices = Invoice.objects.select_related('customer').filter(
            Q(number__icontains=term) | Q(customer__username__icontains=term)
        )
        if not is_staff:
            subs = subs.filter(customer=user).exclude(status=Subscription.Status.DRAFT)
            invoices = invoices.filter(customer=user).exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])

        for s in subs[:5]:
            results.append({'type': 'subscription', 'id': s.id, 'title': s.number, 'subtitle': f'{s.customer.username} · {s.plan.name}', 'status': s.status, 'url': f'/subscriptions/{s.id}'})
        for i in invoices[:5]:
            results.append({'type': 'invoice', 'id': i.id, 'title': i.number, 'subtitle': f'{i.customer.username} · {i.amount}', 'status': i.status, 'url': f'/invoices/{i.id}'})
        if is_staff:
            for c in User.objects.filter(role=User.Role.CUSTOMER).filter(Q(username__icontains=term) | Q(email__icontains=term))[:5]:
                results.append({'type': 'customer', 'id': c.id, 'title': c.username, 'subtitle': c.email, 'status': '', 'url': f'/subscriptions?customer={c.id}'})
        return Response({'results': results})
