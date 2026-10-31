import calendar
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from billing.engine import bill_subscription
from billing.models import Invoice, InvoiceDiscount, Payment
from plans.models import SubscriptionPlan
from pricing.models import Discount, TaxRule
from quotations.models import Quotation, QuotationItem
from subscriptions.models import Subscription, SubscriptionLine

NAMES = ['alice', 'bob', 'carol', 'dave', 'erin', 'frank', 'grace', 'henry']
DUE_TODAY = ['iris', 'jack', 'kate', 'liam']
DEMO_PASSWORD = 'DemoPass123!'


def months_ago(day, months):
    index = day.year * 12 + day.month - 1 - months
    year, month = index // 12, index % 12 + 1
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


def aware(day):
    return timezone.make_aware(datetime.combine(day, time(10, 0)))


class Command(BaseCommand):
    help = 'Create demo customers with subscriptions, invoices, payments, tax and discount rules.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing demo_* users (and their data) first.')

    def handle(self, *args, **options):
        if options['reset']:
            User.objects.filter(username__startswith='demo_').delete()
            for discount in Discount.objects.all():
                discount.times_used = InvoiceDiscount.objects.filter(discount=discount).count()
                discount.save(update_fields=['times_used'])
        if User.objects.filter(username__startswith='demo_').exists():
            self.stdout.write('Demo data already exists. Use --reset to recreate it.')
            return

        today = timezone.localdate()
        plans = [p for p in SubscriptionPlan.objects.select_related('product') if p.is_available_today]
        if not plans:
            raise CommandError('Create at least one available subscription plan first.')

        if not TaxRule.objects.exists():
            TaxRule.objects.create(name='GST 18%', rate=18)
        if not Discount.objects.exists():
            Discount.objects.create(
                name='Volume discount: 10% off for 3+ seats',
                kind=Discount.Kind.PERCENTAGE,
                value=10,
                applies_to=Discount.AppliesTo.SUBSCRIPTION,
                min_quantity=3,
                start_date=today - timedelta(days=150),
                usage_limit=12,
            )

        rng = random.Random(42)
        staff = User.objects.filter(role=User.Role.STAFF).first()
        subscriptions = []

        for index, name in enumerate(NAMES):
            joined = today - timedelta(days=30 * (len(NAMES) - 1 - index) // 1 + rng.randint(0, 6))
            customer = User.objects.create_user(
                username=f'demo_{name}', email=f'{name}@demo.example.com', password=DEMO_PASSWORD, role=User.Role.CUSTOMER
            )
            User.objects.filter(pk=customer.pk).update(date_joined=aware(joined))

            plan = plans[index % len(plans)]
            start = min(joined + timedelta(days=2), today)
            quantity = 1 + index % 3
            status = (
                Subscription.Status.PAUSED if index == 6 else Subscription.Status.CLOSED if index == 7 else Subscription.Status.ACTIVE
            )
            subscription = Subscription.objects.create(
                customer=customer,
                plan=plan,
                quantity=quantity,
                status=Subscription.Status.ACTIVE,
                payment_terms=[Subscription.PaymentTerms.NET_15, Subscription.PaymentTerms.NET_30][index % 2],
                start_date=start,
                expiry_date=today + timedelta(days=20) if index == 2 else start + timedelta(days=365),
                next_billing_date=start,
                created_by=staff,
            )
            SubscriptionLine.objects.create(
                subscription=subscription, product=plan.product, quantity=quantity, unit_price=plan.price
            )
            subscription.log('Subscription created', staff, to_status=Subscription.Status.DRAFT)
            subscription.log('Subscription activated', staff, Subscription.Status.CONFIRMED, Subscription.Status.ACTIVE)
            Subscription.objects.filter(pk=subscription.pk).update(created_at=aware(start))
            subscriptions.append((index, subscription, status))

            # replay history the way it really happened: one billing run on each billing date
            run_date = start
            while run_date <= today:
                bill_subscription(subscription, run_date, staff, confirm=True)
                run_date = plan.next_billing_after(run_date, start)

            invoices = list(subscription.invoices.order_by('period_start'))
            for position, invoice in enumerate(invoices):
                latest = position == len(invoices) - 1
                if latest and index in (1, 3):
                    if index == 1:
                        Invoice.objects.filter(pk=invoice.pk).update(
                            issue_date=today - timedelta(days=40), due_date=today - timedelta(days=25)
                        )
                    continue
                amount = (invoice.amount / 2).quantize(Decimal('0.01')) if latest and index == 2 else invoice.amount
                Payment.objects.create(
                    invoice=invoice,
                    amount=amount,
                    paid_on=min(invoice.issue_date + timedelta(days=rng.randint(1, 5)), today),
                    method=rng.choice(Payment.Method.values),
                    note=rng.choice(['', '', 'Reference confirmed by finance', 'Received via bank statement']),
                    recorded_by=staff,
                )
                invoice.sync_status()

            if status != Subscription.Status.ACTIVE:
                subscription.move_to(status, staff, 'Set up by the demo data')

            if staff and index < 4:
                quotation = Quotation.objects.create(
                    customer=customer,
                    plan=plan,
                    status=Quotation.Status.DRAFT if index % 2 == 0 else Quotation.Status.SENT,
                    created_by=staff,
                )
                QuotationItem.objects.create(
                    quotation=quotation, product=plan.product, quantity=1, unit_price=plan.price, tax_rate=18
                )

        monthly = [p for p in plans if p.billing_frequency == 'monthly'] or plans
        for offset, name in enumerate(DUE_TODAY):
            customer = User.objects.create_user(
                username=f'demo_{name}', email=f'{name}@demo.example.com', password=DEMO_PASSWORD, role=User.Role.CUSTOMER
            )
            plan = monthly[offset % len(monthly)]
            start = months_ago(today, 1)
            User.objects.filter(pk=customer.pk).update(date_joined=aware(start - timedelta(days=2)))
            quantity = 1 + offset
            subscription = Subscription.objects.create(
                customer=customer,
                plan=plan,
                quantity=quantity,
                status=Subscription.Status.ACTIVE,
                payment_terms=Subscription.PaymentTerms.NET_30,
                start_date=start,
                expiry_date=start + timedelta(days=365),
                next_billing_date=start,
                created_by=staff,
            )
            SubscriptionLine.objects.create(
                subscription=subscription, product=plan.product, quantity=quantity, unit_price=plan.price
            )
            subscription.log('Subscription created', staff, to_status=Subscription.Status.DRAFT)
            subscription.log('Subscription activated', staff, Subscription.Status.CONFIRMED, Subscription.Status.ACTIVE)
            Subscription.objects.filter(pk=subscription.pk).update(created_at=aware(start))
            created, _ = bill_subscription(subscription, start, staff, confirm=True)
            for invoice in created:
                Payment.objects.create(
                    invoice=invoice,
                    amount=invoice.amount,
                    paid_on=min(start + timedelta(days=2), today),
                    method=Payment.Method.UPI,
                    recorded_by=staff,
                )
                invoice.sync_status()

        self.stdout.write(self.style.SUCCESS(f'Created {len(NAMES) + len(DUE_TODAY)} demo customers (password: {DEMO_PASSWORD}).'))
