from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def upgrade(apps, schema_editor):
    Subscription = apps.get_model('subscriptions', 'Subscription')
    Line = apps.get_model('subscriptions', 'SubscriptionLine')
    Event = apps.get_model('subscriptions', 'SubscriptionEvent')
    today = timezone.localdate()
    status_map = {'cancelled': 'closed', 'expired': 'closed'}

    for subscription in Subscription.objects.select_related('plan'):
        subscription.status = status_map.get(subscription.status, subscription.status)
        subscription.number = f'SUB-{subscription.pk:05d}'
        if not subscription.expiry_date:
            subscription.expiry_date = subscription.plan.end_date or subscription.start_date + timedelta(days=365)
        if subscription.status == 'closed' and not subscription.end_date:
            subscription.end_date = today
        subscription.save()
        if not Line.objects.filter(subscription=subscription).exists():
            Line.objects.create(
                subscription=subscription,
                product_id=subscription.plan.product_id,
                quantity=subscription.quantity,
                unit_price=subscription.plan.price,
            )
        Event.objects.create(
            subscription=subscription, message='Carried over from the previous version', to_status=subscription.status
        )


class Migration(migrations.Migration):
    dependencies = [('subscriptions', '0003_alter_subscription_options_subscription_created_by_and_more')]

    operations = [migrations.RunPython(upgrade, migrations.RunPython.noop)]
