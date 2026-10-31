from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from config.money import r2
from plans.models import SubscriptionPlan
from products.models import Product, ProductVariant

PAYMENT_TERM_DAYS = {'immediate': 0, 'net_15': 15, 'net_30': 30, 'net_45': 45}
LINE_AMOUNT = ExpressionWrapper(F('quantity') * F('unit_price'), output_field=DecimalField(max_digits=14, decimal_places=2))
FREQUENCY_TO_MONTHLY = {
    'daily': Decimal('365') / 12,
    'weekly': Decimal('52') / 12,
    'monthly': Decimal('1'),
    'quarterly': Decimal('1') / 3,
    'yearly': Decimal('1') / 12,
}


class Subscription(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        QUOTATION = 'quotation', 'Quotation'
        CONFIRMED = 'confirmed', 'Confirmed'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        CLOSED = 'closed', 'Closed'

    class PaymentTerms(models.TextChoices):
        IMMEDIATE = 'immediate', 'Immediate payment'
        NET_15 = 'net_15', 'Net 15 days'
        NET_30 = 'net_30', 'Net 30 days'
        NET_45 = 'net_45', 'Net 45 days'

    TRANSITIONS = {
        Status.DRAFT: [Status.QUOTATION, Status.CONFIRMED, Status.CLOSED],
        Status.QUOTATION: [Status.DRAFT, Status.CONFIRMED, Status.CLOSED],
        Status.CONFIRMED: [Status.ACTIVE, Status.CLOSED],
        Status.ACTIVE: [Status.PAUSED, Status.CLOSED],
        Status.PAUSED: [Status.ACTIVE, Status.CLOSED],
        Status.CLOSED: [],
    }

    number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    payment_terms = models.CharField(max_length=20, choices=PaymentTerms.choices, default=PaymentTerms.NET_15)
    start_date = models.DateField(default=timezone.localdate)
    expiry_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True, help_text='Date the subscription was closed')
    next_billing_date = models.DateField(null=True, blank=True, db_index=True)
    billing_anchor = models.DateField(
        null=True, blank=True, help_text='Billing cycles keep this day of the month. Defaults to the start date.'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.number} - {self.customer}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            self.number = f'SUB-{self.pk:05d}'
            super().save(update_fields=['number'])

    @property
    def anchor_date(self):
        return self.billing_anchor or self.start_date

    @property
    def payment_term_days(self):
        return PAYMENT_TERM_DAYS[self.payment_terms]

    @property
    def cycle_subtotal(self):
        total = self.lines.aggregate(total=Sum(LINE_AMOUNT))['total']
        return total if total is not None else Decimal('0.00')

    @property
    def monthly_value(self):
        return r2(self.cycle_subtotal * FREQUENCY_TO_MONTHLY[self.plan.billing_frequency])

    def can_transition(self, to_status):
        return to_status in self.TRANSITIONS[self.Status(self.status)]

    def log(self, message, actor=None, from_status='', to_status=''):
        return SubscriptionEvent.objects.create(
            subscription=self, message=message, actor=actor, from_status=from_status, to_status=to_status
        )

    def move_to(self, to_status, actor=None, message=''):
        if not self.can_transition(to_status):
            raise ValueError(f'Cannot move a {self.status} subscription to {to_status}.')
        previous = self.status
        self.status = to_status
        update = ['status']
        if to_status == self.Status.CLOSED:
            self.end_date = timezone.localdate()
            update.append('end_date')
        self.save(update_fields=update)
        self.log(message or f'Status changed from {previous} to {to_status}', actor, previous, to_status)


class SubscriptionLine(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text='Blank means use the admin tax rules'
    )

    @property
    def amount(self):
        return self.quantity * self.unit_price


class SubscriptionEvent(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='events')
    message = models.CharField(max_length=255)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']


def activate_due_subscriptions(today=None):
    """Confirmed subscriptions whose start date has arrived become active."""
    today = today or timezone.localdate()
    due = list(Subscription.objects.filter(status=Subscription.Status.CONFIRMED, start_date__lte=today))
    for subscription in due:
        subscription.next_billing_date = subscription.next_billing_date or subscription.start_date
        subscription.move_to(Subscription.Status.ACTIVE, message='Activated automatically on its start date')
        subscription.save(update_fields=['next_billing_date'])
    return len(due)


def close_expired_subscriptions(today=None):
    """Plans with automatic closure close their subscriptions once the expiry date has passed."""
    today = today or timezone.localdate()
    expired = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.PAUSED],
        expiry_date__lt=today,
        plan__auto_close_enabled=True,
    ).select_related('plan')
    closed = 0
    for subscription in expired:
        subscription.move_to(Subscription.Status.CLOSED, message='Closed automatically at expiry')
        closed += 1
    return closed
