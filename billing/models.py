from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from pricing.models import Discount
from products.models import Product
from subscriptions.models import Subscription
from config.money import r2



class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        CONFIRMED = 'confirmed', 'Confirmed'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'

    number = models.CharField(max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invoices')
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(db_index=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='Grand total')
    notes = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_reminder_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['subscription', 'period_start'],
                condition=Q(period_start__isnull=False) & ~Q(status='cancelled'),
                name='one_invoice_per_subscription_period',
            )
        ]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            self.number = f'INV-{self.pk:05d}'
            super().save(update_fields=['number'])

    @property
    def amount_paid(self):
        return self.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    @property
    def balance(self):
        return self.amount - self.amount_paid

    @property
    def is_overdue(self):
        return self.status == self.Status.CONFIRMED and self.due_date < timezone.localdate()

    def recalculate(self):
        lines = list(self.lines.all())
        self.subtotal = sum((line.subtotal for line in lines), Decimal('0.00'))
        self.discount_total = sum((line.discount_amount for line in lines), Decimal('0.00'))
        self.tax_total = sum((line.tax for line in lines), Decimal('0.00'))
        self.amount = self.subtotal - self.discount_total + self.tax_total
        self.save(update_fields=['subtotal', 'discount_total', 'tax_total', 'amount'])

    def sync_status(self):
        if self.status in (self.Status.CONFIRMED, self.Status.PAID):
            self.status = self.Status.PAID if self.balance <= 0 else self.Status.CONFIRMED
            self.save(update_fields=['status'])


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    @property
    def subtotal(self):
        return r2(self.quantity * self.unit_price)

    @property
    def net(self):
        return self.subtotal - self.discount_amount

    @property
    def tax(self):
        return r2(self.net * self.tax_rate / Decimal('100'))

    @property
    def total(self):
        return self.net + self.tax


class InvoiceDiscount(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='discounts')
    discount = models.ForeignKey(Discount, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=12, decimal_places=2)


class Payment(models.Model):
    class Method(models.TextChoices):
        CARD = 'card', 'Card'
        BANK_TRANSFER = 'bank_transfer', 'Bank transfer'
        UPI = 'upi', 'UPI'
        CASH = 'cash', 'Cash'
        CHEQUE = 'cheque', 'Cheque'

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_on = models.DateField(default=timezone.localdate, db_index=True)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CARD)
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_on', '-id']

    def __str__(self):
        return f'{self.invoice.number} - {self.amount}'
