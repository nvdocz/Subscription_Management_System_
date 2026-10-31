from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from config.money import r2
from products.models import Product


class TaxRule(models.Model):
    """Admin-defined tax. The most specific rule wins: product, then product type, then all products."""

    name = models.CharField(max_length=120)
    rate = models.DecimalField(max_digits=5, decimal_places=2, help_text='Percentage, e.g. 18.00')
    product_type = models.CharField(max_length=20, choices=Product.ProductType.choices, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name='tax_rules')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_active', 'name']

    def __str__(self):
        return f'{self.name} ({self.rate}%)'

    @property
    def scope(self):
        if self.product_id:
            return 'product'
        return 'product_type' if self.product_type else 'all'


def tax_rate_for(product):
    """Resolve the tax percentage for a product from the active admin rules."""
    rules = TaxRule.objects.filter(is_active=True)
    for matcher in (
        rules.filter(product=product),
        rules.filter(product__isnull=True, product_type=product.product_type),
        rules.filter(product__isnull=True, product_type=''),
    ):
        rule = matcher.order_by('-rate').first()
        if rule is not None:
            return rule.rate
    return Decimal('0.00')


class Discount(models.Model):
    class Kind(models.TextChoices):
        FIXED = 'fixed', 'Fixed amount'
        PERCENTAGE = 'percentage', 'Percentage'

    class AppliesTo(models.TextChoices):
        PRODUCTS = 'products', 'Specific products'
        SUBSCRIPTION = 'subscription', 'Whole subscription'

    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    applies_to = models.CharField(max_length=20, choices=AppliesTo.choices, default=AppliesTo.SUBSCRIPTION)
    products = models.ManyToManyField(Product, blank=True, related_name='discounts')
    min_purchase = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_quantity = models.PositiveIntegerField(default=0)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def status(self):
        today = timezone.localdate()
        if not self.is_active:
            return 'disabled'
        if self.usage_limit is not None and self.times_used >= self.usage_limit:
            return 'exhausted'
        if self.end_date and self.end_date < today:
            return 'expired'
        if self.start_date > today:
            return 'scheduled'
        return 'active'

    def usable_on(self, date):
        if not self.is_active or self.start_date > date or (self.end_date and self.end_date < date):
            return False
        return self.usage_limit is None or self.times_used < self.usage_limit

    def amount_for(self, base):
        if self.kind == self.Kind.PERCENTAGE:
            return r2(base * self.value / Decimal('100'))
        return min(self.value, base)
