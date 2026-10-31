from django.utils import timezone
from rest_framework import serializers

from accounts.serializers import UserSerializer

from .models import Invoice, InvoiceDiscount, InvoiceLine, Payment


class InvoiceLineSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    tax = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = InvoiceLine
        fields = ('id', 'description', 'quantity', 'unit_price', 'tax_rate', 'discount_amount', 'subtotal', 'tax', 'total')
        read_only_fields = fields


class InvoiceDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceDiscount
        fields = ('id', 'name', 'amount')
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.number', read_only=True)
    customer_name = serializers.CharField(source='invoice.customer.username', read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id', 'invoice', 'invoice_number', 'customer_name', 'amount', 'paid_on', 'method', 'note', 'created_at',
        )
        read_only_fields = ('id', 'created_at')

    def validate(self, attrs):
        invoice = attrs['invoice']
        if invoice.status != Invoice.Status.CONFIRMED:
            raise serializers.ValidationError({'invoice': 'Payments can only be recorded against confirmed invoices.'})
        if attrs['amount'] <= 0:
            raise serializers.ValidationError({'amount': 'Amount must be greater than zero.'})
        paid_on = attrs.get('paid_on') or timezone.localdate()
        if paid_on > timezone.localdate():
            raise serializers.ValidationError({'paid_on': 'A payment cannot be dated in the future.'})
        if paid_on < invoice.issue_date:
            raise serializers.ValidationError({'paid_on': f'A payment cannot be dated before the invoice was issued ({invoice.issue_date}).'})
        if attrs['amount'] > invoice.balance:
            raise serializers.ValidationError({'amount': f'Amount exceeds the outstanding balance ({invoice.balance}).'})
        return attrs

    def create(self, validated_data):
        payment = super().create(validated_data)
        payment.invoice.sync_status()
        return payment


class InvoiceListSerializer(serializers.ModelSerializer):
    customer_detail = UserSerializer(source='customer', read_only=True)
    subscription_number = serializers.CharField(source='subscription.number', read_only=True, default=None)
    plan_name = serializers.CharField(source='subscription.plan.name', read_only=True, default=None)
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = (
            'id', 'number', 'customer', 'customer_detail', 'subscription', 'subscription_number', 'plan_name',
            'status', 'issue_date', 'due_date', 'period_start', 'period_end', 'subtotal', 'discount_total',
            'tax_total', 'amount', 'amount_paid', 'balance', 'is_overdue', 'sent_at', 'created_at',
        )
        read_only_fields = fields


class InvoiceDetailSerializer(InvoiceListSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    discounts = InvoiceDiscountSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    allowed_actions = serializers.SerializerMethodField()

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + ('notes', 'last_reminder_at', 'lines', 'discounts', 'payments', 'allowed_actions')
        read_only_fields = fields

    def get_allowed_actions(self, invoice):
        from .views import allowed_invoice_actions

        return allowed_invoice_actions(invoice, self.context['request'].user)
