from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from subscriptions import services as subscription_services
from subscriptions.models import Subscription

from .models import Quotation


def convert_quotation(quotation, actor):
    """Turn an accepted quotation into a subscription, replacing the customer's current plan for that product."""
    if quotation.status != Quotation.Status.ACCEPTED:
        raise ValidationError('Only accepted quotations can be converted to a subscription.')
    if quotation.subscription_id:
        raise ValidationError('This quotation has already been converted.')
    plan = quotation.plan
    if plan is None:
        raise ValidationError('This quotation has no subscription plan selected.')
    today = timezone.localdate()
    if not plan.is_active:
        raise ValidationError('This plan is switched off and cannot be sold.')
    if plan.end_date and plan.end_date < today:
        raise ValidationError('This plan is no longer available.')
    subscription_services.check_minimum_quantity(
        plan, [{'product': item.product, 'quantity': item.quantity} for item in quotation.items.select_related('product')]
    )

    live = Subscription.objects.filter(
        customer=quotation.customer, status__in=[Subscription.Status.ACTIVE, Subscription.Status.PAUSED]
    )
    if live.filter(plan=plan).exists():
        raise ValidationError('The customer already has an active subscription to this plan.')

    start_date = max(today, plan.start_date)
    with transaction.atomic():
        for old in live.filter(plan__product=plan.product):
            old.move_to(Subscription.Status.CLOSED, actor, f'Replaced by {plan.name} (plan change)')
        subscription = Subscription.objects.create(
            customer=quotation.customer,
            plan=plan,
            quantity=plan.min_quantity,
            status=Subscription.Status.DRAFT,
            payment_terms=quotation.payment_terms,
            start_date=start_date,
            expiry_date=subscription_services.default_expiry(plan, start_date),
            created_by=actor,
        )
        subscription_services.create_lines(
            subscription,
            [
                {
                    'product': item.product,
                    'variant': item.variant,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'tax_rate': item.tax_rate,
                }
                for item in quotation.items.select_related('product', 'variant')
            ],
        )
        subscription.log(f'Created from quotation #{quotation.pk}', actor, to_status=Subscription.Status.DRAFT)
        quotation.subscription = subscription
        quotation.save(update_fields=['subscription'])
        subscription_services.confirm(subscription, actor)
    return subscription
