"""Aggregate queries behind the dashboards and reports. Everything here is set-based (no per-row loops) so it
stays fast with thousands of subscriptions and invoices."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from billing.models import Invoice, Payment
from subscriptions.models import FREQUENCY_TO_MONTHLY, LINE_AMOUNT, Subscription, SubscriptionLine

ZERO = Decimal('0.00')
MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
LIVE = [Subscription.Status.ACTIVE, Subscription.Status.PAUSED]


def month_buckets(count, today=None):
    today = today or timezone.localdate()
    base = today.year * 12 + today.month - 1
    return [((base - i) // 12, (base - i) % 12 + 1) for i in range(count - 1, -1, -1)]


def month_label(bucket):
    return f'{MONTH_NAMES[bucket[1] - 1]} {str(bucket[0])[2:]}'


def first_of(bucket):
    return timezone.localdate().replace(year=bucket[0], month=bucket[1], day=1)


def monthly_value(lines):
    """Sum of recurring line amounts normalised to a month. ``lines`` is a SubscriptionLine queryset."""
    rows = lines.values('subscription__plan__billing_frequency').annotate(total=Sum(LINE_AMOUNT))
    return sum(
        (r['total'] * FREQUENCY_TO_MONTHLY[r['subscription__plan__billing_frequency']] for r in rows if r['total']),
        ZERO,
    ).quantize(Decimal('0.01'))


def current_mrr():
    return monthly_value(SubscriptionLine.objects.filter(subscription__status=Subscription.Status.ACTIVE))


def invoice_buckets(invoices=None):
    invoices = Invoice.objects.all() if invoices is None else invoices
    today = timezone.localdate()
    confirmed = invoices.filter(status=Invoice.Status.CONFIRMED)
    paid_by_invoice = confirmed.annotate(paid=Sum('payments__amount'))
    outstanding = [(i.amount - (i.paid or ZERO), i.due_date) for i in paid_by_invoice.only('amount', 'due_date')]
    overdue = [amount for amount, due in outstanding if due < today]
    return {
        'outstanding': {'count': len(outstanding), 'amount': sum((a for a, _ in outstanding), ZERO)},
        'overdue': {'count': len(overdue), 'amount': sum(overdue, ZERO)},
    }


def revenue_by_month(count, invoices_payments=None):
    buckets = month_buckets(count)
    payments = Payment.objects.all() if invoices_payments is None else invoices_payments
    rows = (
        payments.filter(paid_on__gte=first_of(buckets[0]))
        .annotate(month=TruncMonth('paid_on'))
        .values('month')
        .annotate(total=Sum('amount'))
    )
    totals = {(r['month'].year, r['month'].month): r['total'] for r in rows}
    return [{'label': month_label(b), 'revenue': totals.get(b, ZERO)} for b in buckets]


def subscription_growth(count):
    buckets = month_buckets(count)
    first = first_of(buckets[0])
    live_ever = Subscription.objects.exclude(
        status__in=[Subscription.Status.DRAFT, Subscription.Status.QUOTATION, Subscription.Status.CONFIRMED]
    )
    running = live_ever.filter(start_date__lt=first).count()
    rows = (
        live_ever.filter(start_date__gte=first)
        .annotate(month=TruncMonth('start_date'))
        .values('month')
        .annotate(n=Count('id'))
    )
    new_per_month = {(r['month'].year, r['month'].month): r['n'] for r in rows}
    result = []
    for b in buckets:
        new = new_per_month.get(b, 0)
        running += new
        result.append({'label': month_label(b), 'new': new, 'total': running})
    return result


def mrr_movement(count):
    """New and churned monthly recurring revenue per month, with the running MRR."""
    buckets = month_buckets(count)
    first = first_of(buckets[0])
    started_states = [Subscription.Status.ACTIVE, Subscription.Status.PAUSED, Subscription.Status.CLOSED]

    def by_month(queryset, date_field):
        rows = (
            queryset.annotate(month=TruncMonth(date_field))
            .values('month', 'subscription__plan__billing_frequency')
            .annotate(total=Sum(LINE_AMOUNT))
        )
        out = {}
        for r in rows:
            key = (r['month'].year, r['month'].month)
            out[key] = out.get(key, ZERO) + r['total'] * FREQUENCY_TO_MONTHLY[r['subscription__plan__billing_frequency']]
        return out

    new = by_month(
        SubscriptionLine.objects.filter(subscription__status__in=started_states, subscription__start_date__gte=first),
        'subscription__start_date',
    )
    churned = by_month(
        SubscriptionLine.objects.filter(subscription__status=Subscription.Status.CLOSED, subscription__end_date__gte=first),
        'subscription__end_date',
    )
    before_new = monthly_value(
        SubscriptionLine.objects.filter(subscription__status__in=started_states, subscription__start_date__lt=first)
    )
    before_churn = monthly_value(
        SubscriptionLine.objects.filter(
            subscription__status=Subscription.Status.CLOSED, subscription__start_date__lt=first, subscription__end_date__lt=first
        )
    )
    running = before_new - before_churn
    result = []
    for b in buckets:
        n, c = new.get(b, ZERO), churned.get(b, ZERO)
        running += n - c
        result.append(
            {
                'label': month_label(b),
                'new': n.quantize(Decimal('0.01')),
                'churned': -c.quantize(Decimal('0.01')),
                'mrr': running.quantize(Decimal('0.01')),
            }
        )
    return result


def status_breakdown():
    counts = {r['status']: r['count'] for r in Subscription.objects.values('status').annotate(count=Count('id'))}
    return [{'status': value, 'label': label, 'count': counts.get(value, 0)} for value, label in Subscription.Status.choices]


def invoice_status_breakdown(invoices=None):
    invoices = Invoice.objects.all() if invoices is None else invoices
    counts = {r['status']: r['count'] for r in invoices.values('status').annotate(count=Count('id'))}
    overdue = invoices.filter(status=Invoice.Status.CONFIRMED, due_date__lt=timezone.localdate()).count()
    return [
        {'status': 'paid', 'label': 'Paid', 'count': counts.get('paid', 0)},
        {'status': 'confirmed', 'label': 'Outstanding', 'count': counts.get('confirmed', 0) - overdue},
        {'status': 'overdue', 'label': 'Overdue', 'count': overdue},
        {'status': 'draft', 'label': 'Draft', 'count': counts.get('draft', 0)},
        {'status': 'cancelled', 'label': 'Cancelled', 'count': counts.get('cancelled', 0)},
    ]


def payment_method_mix(payments=None):
    payments = Payment.objects.all() if payments is None else payments
    labels = dict(Payment.Method.choices)
    rows = payments.values('method').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')
    return [{'method': r['method'], 'label': labels[r['method']], 'amount': r['total'], 'count': r['count']} for r in rows]


def aging_buckets():
    today = timezone.localdate()
    buckets = {'Not yet due': ZERO, '1-30 days': ZERO, '31-60 days': ZERO, '60+ days': ZERO}
    confirmed = Invoice.objects.filter(status=Invoice.Status.CONFIRMED).annotate(paid=Sum('payments__amount'))
    for invoice in confirmed.only('amount', 'due_date'):
        late = (today - invoice.due_date).days
        label = 'Not yet due' if late <= 0 else '1-30 days' if late <= 30 else '31-60 days' if late <= 60 else '60+ days'
        buckets[label] += invoice.amount - (invoice.paid or ZERO)
    return [{'label': label, 'amount': amount} for label, amount in buckets.items()]


def billing_forecast(days=30):
    today = timezone.localdate()
    due = Subscription.objects.filter(
        status=Subscription.Status.ACTIVE, next_billing_date__gte=today, next_billing_date__lte=today + timedelta(days=days)
    )
    amount = SubscriptionLine.objects.filter(subscription__in=due).aggregate(total=Sum(LINE_AMOUNT))['total'] or ZERO
    return {'count': due.count(), 'amount': amount}


def overdue_rows(limit=8):
    today = timezone.localdate()
    rows = (
        Invoice.objects.filter(status=Invoice.Status.CONFIRMED, due_date__lt=today)
        .select_related('customer')
        .annotate(paid=Sum('payments__amount'))
        .order_by('due_date')[:limit]
    )
    return [
        {
            'id': i.id,
            'number': i.number,
            'customer': i.customer.username,
            'due_date': i.due_date,
            'days_overdue': (today - i.due_date).days,
            'balance': i.amount - (i.paid or ZERO),
        }
        for i in rows
    ]


def collection_rate():
    month_start = timezone.localdate().replace(day=1)
    billed = Invoice.objects.filter(issue_date__gte=month_start).exclude(
        status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED]
    ).aggregate(total=Sum('amount'))['total'] or ZERO
    collected = Payment.objects.filter(paid_on__gte=month_start).aggregate(total=Sum('amount'))['total'] or ZERO
    return {'billed': billed, 'collected': collected}


def in_period(queryset, field, start, end):
    if start:
        queryset = queryset.filter(**{f'{field}__gte': start})
    if end:
        queryset = queryset.filter(**{f'{field}__lte': end})
    return queryset


def live_subscription_count():
    return Subscription.objects.filter(status__in=LIVE).count()


def count_closed_since(days):
    since = timezone.localdate() - timedelta(days=days)
    return Subscription.objects.filter(status=Subscription.Status.CLOSED, end_date__gte=since).count()

