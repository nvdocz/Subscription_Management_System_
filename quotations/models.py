from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from config.money import r2
from plans.models import SubscriptionPlan
from products.models import Product, ProductVariant
from subscriptions.models import Subscription


class QuotationTemplate(models.Model):
    name = models.CharField(max_length=255)
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='templates'
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class QuotationTemplateItem(models.Model):
    template = models.ForeignKey(QuotationTemplate, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)


class Quotation(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SENT = 'sent', 'Sent'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        EXPIRED = 'expired', 'Expired'

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quotations')
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='quotations'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    validity_days = models.PositiveIntegerField(default=15)
    payment_terms = models.CharField(max_length=20, choices=Subscription.PaymentTerms.choices, default=Subscription.PaymentTerms.NET_15)
    issued_date = models.DateField(default=timezone.localdate, editable=False)
    notes = models.TextField(blank=True)
    subscription = models.OneToOneField(
        Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='quotation'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_quotations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Quotation #{self.pk} for {self.customer}'

    @property
    def valid_until(self):
        return self.issued_date + timedelta(days=self.validity_days)

    @property
    def is_expired(self):
        return timezone.localdate() > self.valid_until

    def refresh_status(self):
        if self.status in (self.Status.DRAFT, self.Status.SENT) and self.is_expired:
            self.status = self.Status.EXPIRED
            self.save(update_fields=['status'])

    @property
    def subtotal(self):
        return sum((item.line_subtotal for item in self.items.all()), Decimal('0.00'))

    @property
    def tax_total(self):
        return sum((item.line_tax for item in self.items.all()), Decimal('0.00'))

    @property
    def total(self):
        return self.subtotal + self.tax_total


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    @property
    def line_subtotal(self):
        return self.quantity * self.unit_price

    @property
    def line_tax(self):
        return r2(self.line_subtotal * self.tax_rate / Decimal('100'))

    @property
    def line_total(self):
        return self.line_subtotal + self.line_tax
