import calendar
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models

from config.money import r2

from products.models import Product


class SubscriptionPlan(models.Model):
    class BillingFrequency(models.TextChoices):
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'
        QUARTERLY = 'quarterly', 'Quarterly'
        YEARLY = 'yearly', 'Yearly'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='plans')
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_frequency = models.CharField(max_length=20, choices=BillingFrequency.choices)
    min_quantity = models.PositiveIntegerField(default=1)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    auto_close_enabled = models.BooleanField(default=False)
    allow_early_closure = models.BooleanField(default=True)
    allow_pause = models.BooleanField(default=True)
    allow_renewal = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product__name', 'price']

    def __str__(self):
        return f'{self.name} ({self.get_billing_frequency_display()})'

    @property
    def monthly_equivalent(self):
        factor = {'daily': Decimal('365') / 12, 'weekly': Decimal('52') / 12, 'monthly': Decimal('1'), 'quarterly': Decimal('1') / 3, 'yearly': Decimal('1') / 12}
        return r2(self.price * factor[self.billing_frequency])

    @property
    def is_available_today(self):
        from django.utils import timezone

        today = timezone.localdate()
        return self.is_active and self.start_date <= today and (self.end_date is None or self.end_date >= today)

    def next_billing_after(self, date, anchor=None):
        """Next billing date after ``date``. Monthly and longer schedules keep the day of ``anchor`` (usually the
        start date) so a 31st never drifts to the 28th."""
        if self.billing_frequency == 'daily':
            return date + timedelta(days=1)
        if self.billing_frequency == 'weekly':
            return date + timedelta(days=7)
        months = {'monthly': 1, 'quarterly': 3, 'yearly': 12}[self.billing_frequency]
        month_index = date.month - 1 + months
        year, month = date.year + month_index // 12, month_index % 12 + 1
        day = (anchor or date).day
        return date.replace(year=year, month=month, day=min(day, calendar.monthrange(year, month)[1]))
