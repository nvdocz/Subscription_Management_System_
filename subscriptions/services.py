"""Subscription lifecycle: Draft -> Quotation -> Confirmed -> Active -> Closed (with Pause and Renew)."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from billing.engine import bill_subscription

from .models import Subscription, SubscriptionLine

S = Subscription.Status


def check_minimum_quantity(plan, lines):
    """The plan's product must be bought in at least the plan's minimum quantity."""
    bought = sum(int(line.get('quantity', 1)) for line in lines if line['product'].pk == plan.product_id)
    if bought < plan.min_quantity:
        raise ValidationError(
            f'The {plan.name} plan needs at least {plan.min_quantity} of {plan.product.name}. '
            f'These lines only include {bought}.'
        )


def default_expiry(plan, start_date):
    return plan.end_date or (start_date + timedelta(days=365))


def allowed_actions(subscription, user):
    """Actions the given user may perform now. Customers are limited by the plan's lifecycle options."""
    plan, status = subscription.plan, subscription.status
    if user.role == User.Role.CUSTOMER:
        if subscription.customer_id != user.id:
            return []
        actions = []
        if status == S.ACTIVE and plan.allow_pause:
            actions.append('pause')
        if status == S.PAUSED and plan.allow_pause:
            actions.append('resume')
        if status in (S.ACTIVE, S.PAUSED) and plan.allow_early_closure:
            actions.append('close')
        if status in (S.ACTIVE, S.CLOSED) and plan.allow_renewal and plan.is_active:
            actions.append('renew')
        return actions

    actions = {
        S.DRAFT: ['send_quotation', 'confirm', 'close'],
        S.QUOTATION: ['confirm', 'close'],
        S.CONFIRMED: ['activate', 'close'],
        S.ACTIVE: ['pause', 'close', 'renew'],
        S.PAUSED: ['resume', 'close'],
        S.CLOSED: ['renew'],
    }[S(status)]
    return actions


def perform(subscription, action, user):
    if action not in allowed_actions(subscription, user):
        raise PermissionDenied(f'You cannot {action.replace("_", " ")} this subscription right now.')
    return {
        'send_quotation': send_quotation,
        'confirm': confirm,
        'activate': activate,
        'pause': pause,
        'resume': resume,
        'close': close,
        'renew': renew,
    }[action](subscription, user)


def send_quotation(subscription, actor):
    if not subscription.lines.exists():
        raise ValidationError('Add at least one line before sending a quotation.')
    subscription.move_to(S.QUOTATION, actor, 'Quotation sent to the customer')
    return subscription


def confirm(subscription, actor):
    if not subscription.lines.exists():
        raise ValidationError('Add at least one line before confirming.')
    if not subscription.plan.is_active:
        raise ValidationError('This plan is switched off and cannot be sold.')
    if subscription.plan.end_date and subscription.plan.end_date < timezone.localdate():
        raise ValidationError('This plan is no longer available.')
    subscription.move_to(S.CONFIRMED, actor, 'Subscription confirmed')
    if subscription.start_date <= timezone.localdate():
        activate(subscription, actor)
    return subscription


def activate(subscription, actor):
    today = timezone.localdate()
    if subscription.start_date > today:
        raise ValidationError(f'This subscription starts on {subscription.start_date:%d %b %Y}.')
    with transaction.atomic():
        subscription.move_to(S.ACTIVE, actor, 'Subscription activated')
        subscription.next_billing_date = subscription.next_billing_date or subscription.start_date
        subscription.save(update_fields=['next_billing_date'])
        created, _ = bill_subscription(subscription, today, actor, confirm=True)
        if created:
            subscription.log(f'First invoice {created[0].number} issued', actor)
    return subscription


def pause(subscription, actor):
    subscription.move_to(S.PAUSED, actor, 'Subscription paused. Billing is on hold')
    return subscription


def resume(subscription, actor):
    subscription.move_to(S.ACTIVE, actor, 'Subscription resumed')
    today = timezone.localdate()
    if subscription.next_billing_date and subscription.next_billing_date < today:
        subscription.next_billing_date = today
        subscription.billing_anchor = today
        subscription.save(update_fields=['next_billing_date', 'billing_anchor'])
    return subscription


def close(subscription, actor):
    subscription.move_to(S.CLOSED, actor, 'Subscription closed')
    return subscription


def renew(subscription, actor):
    today = timezone.localdate()
    base = max(subscription.expiry_date or today, today)
    subscription.expiry_date = base + timedelta(days=365)
    previous = subscription.status
    subscription.status = S.ACTIVE
    subscription.end_date = None
    if previous == S.CLOSED:
        subscription.next_billing_date = today
        subscription.billing_anchor = today
    subscription.save(update_fields=['expiry_date', 'status', 'end_date', 'next_billing_date', 'billing_anchor'])
    subscription.log(f'Renewed until {subscription.expiry_date:%d %b %Y}', actor, previous, S.ACTIVE)
    if previous == S.CLOSED:
        bill_subscription(subscription, today, actor, confirm=True)
    return subscription


def create_lines(subscription, lines_data):
    for data in lines_data:
        SubscriptionLine.objects.create(
            subscription=subscription,
            product=data['product'],
            variant=data.get('variant'),
            quantity=data.get('quantity', 1),
            unit_price=data['unit_price'],
            tax_rate=data.get('tax_rate'),
        )
