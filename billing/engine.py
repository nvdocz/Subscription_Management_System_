"""Recurring billing: builds invoices straight from subscriptions.

Each billing period of a subscription is invoiced exactly once (enforced by a database constraint and by
advancing ``next_billing_date``), taxes come from the admin tax rules and discounts apply on their own.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Case, F, IntegerField, Q, Sum, When
from django.utils import timezone

from config.money import r2
from pricing.models import Discount, tax_rate_for
from subscriptions.models import (
    LINE_AMOUNT,
    Subscription,
    SubscriptionLine,
    activate_due_subscriptions,
    close_expired_subscriptions,
)

from .models import Invoice, InvoiceDiscount, InvoiceLine

MAX_PERIODS_PER_RUN = 12


def apply_discounts(invoice, lines, on_date):
    # Percentages come off the list price first, fixed amounts after, oldest rule first, so the result never
    # depends on the order rules happened to be created in.
    kind_order = Case(When(kind=Discount.Kind.PERCENTAGE, then=0), default=1, output_field=IntegerField())
    candidates = (
        Discount.objects.filter(is_active=True, start_date__lte=on_date)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=on_date))
        .prefetch_related('products')
        .order_by(kind_order, 'id')
    )
    for discount in candidates:
        if not discount.usable_on(on_date):
            continue
        if discount.applies_to == Discount.AppliesTo.PRODUCTS:
            product_ids = {p.id for p in discount.products.all()}
            matched = [line for line in lines if line.product_id in product_ids]
        else:
            matched = list(lines)
        if not matched:
            continue
        quantity = sum(line.quantity for line in matched)
        base = sum((line.net for line in matched), Decimal('0.00'))
        if base <= 0 or quantity < discount.min_quantity or base < discount.min_purchase:
            continue
        amount = discount.amount_for(base)
        if amount <= 0:
            continue

        claimed = (
            Discount.objects.filter(pk=discount.pk)
            .filter(Q(usage_limit__isnull=True) | Q(times_used__lt=F('usage_limit')))
            .update(times_used=F('times_used') + 1)
        )
        if not claimed:
            continue

        remaining = amount
        for index, line in enumerate(matched):
            share = remaining if index == len(matched) - 1 else r2(line.net / base * amount)
            share = min(share, line.net)
            line.discount_amount += share
            remaining -= share
        InvoiceDiscount.objects.create(invoice=invoice, discount=discount, name=discount.name, amount=amount - remaining)


def build_invoice(subscription, period_start, actor=None, confirm=False, issue_date=None):
    plan = subscription.plan
    issue_date = issue_date or period_start
    period_end = plan.next_billing_after(period_start, subscription.anchor_date) - timedelta(days=1)
    invoice = Invoice.objects.create(
        customer=subscription.customer,
        subscription=subscription,
        status=Invoice.Status.DRAFT,
        issue_date=issue_date,
        due_date=issue_date + timedelta(days=subscription.payment_term_days),
        period_start=period_start,
        period_end=period_end,
        amount=0,
        created_by=actor,
    )
    lines = []
    for sub_line in subscription.lines.select_related('product', 'variant'):
        rate = sub_line.tax_rate if sub_line.tax_rate is not None else tax_rate_for(sub_line.product)
        label = sub_line.product.name + (f' ({sub_line.variant.name})' if sub_line.variant else '')
        lines.append(
            InvoiceLine.objects.create(
                invoice=invoice,
                product=sub_line.product,
                description=f'{label}, {period_start:%d %b} to {period_end:%d %b %Y}',
                quantity=sub_line.quantity,
                unit_price=sub_line.unit_price,
                tax_rate=rate,
            )
        )
    apply_discounts(invoice, lines, issue_date)
    for line in lines:
        line.save(update_fields=['discount_amount'])
    invoice.recalculate()
    if confirm:
        invoice.status = Invoice.Status.CONFIRMED
        invoice.save(update_fields=['status'])
    return invoice


def bill_subscription(subscription, as_of=None, actor=None, confirm=False):
    """Create an invoice for every unbilled period that is due. Returns (created_invoices, skipped_periods)."""
    as_of = as_of or timezone.localdate()
    created, skipped = [], 0
    while (
        subscription.next_billing_date
        and subscription.next_billing_date <= as_of
        and len(created) + skipped < MAX_PERIODS_PER_RUN
    ):
        period_start = subscription.next_billing_date
        if subscription.expiry_date and period_start > subscription.expiry_date:
            break
        with transaction.atomic():
            already = Invoice.objects.filter(subscription=subscription, period_start=period_start).exclude(
                status=Invoice.Status.CANCELLED
            )
            if already.exists():
                skipped += 1
            else:
                created.append(build_invoice(subscription, period_start, actor, confirm, issue_date=as_of))
            subscription.next_billing_date = subscription.plan.next_billing_after(period_start, subscription.anchor_date)
            subscription.save(update_fields=['next_billing_date'])
    return created, skipped


def due_subscriptions(as_of):
    """Active subscriptions with a billing period to invoice. Periods that start after expiry are not billable."""
    return (
        Subscription.objects.filter(status=Subscription.Status.ACTIVE, next_billing_date__lte=as_of)
        .filter(Q(expiry_date__isnull=True) | Q(next_billing_date__lte=F('expiry_date')))
        .select_related('plan', 'customer')
    )


def preview_billing(as_of=None):
    as_of = as_of or timezone.localdate()
    due = due_subscriptions(as_of)
    amounts = dict(
        SubscriptionLine.objects.filter(subscription__in=due)
        .values_list('subscription_id')
        .annotate(total=Sum(LINE_AMOUNT))
    )
    rows = [
        {
            'subscription': s.id,
            'number': s.number,
            'customer': s.customer.username,
            'plan': s.plan.name,
            'billing_date': s.next_billing_date,
            'estimated_amount': amounts.get(s.id, Decimal('0.00')),
        }
        for s in due.order_by('next_billing_date')[:200]
    ]
    return {
        'as_of': as_of,
        'due_count': due.count(),
        'estimated_total': sum(amounts.values(), Decimal('0.00')),
        'rows': rows,
    }


def run_billing(as_of=None, actor=None, confirm=False):
    as_of = as_of or timezone.localdate()
    activated = activate_due_subscriptions(as_of)
    closed = close_expired_subscriptions(as_of)
    invoices, skipped = [], 0
    for subscription in due_subscriptions(as_of):
        created, skipped_here = bill_subscription(subscription, as_of, actor, confirm)
        invoices.extend(created)
        skipped += skipped_here
    return {
        'as_of': as_of,
        'activated': activated,
        'auto_closed': closed,
        'invoices_created': len(invoices),
        'periods_skipped': skipped,
        'total_billed': sum((i.amount for i in invoices), Decimal('0.00')),
        'invoices': [
            {'id': i.id, 'number': i.number, 'customer': i.customer.username, 'amount': i.amount} for i in invoices[:100]
        ],
    }

