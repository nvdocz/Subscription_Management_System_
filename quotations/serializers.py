from rest_framework import serializers

from accounts.models import User
from accounts.serializers import UserSerializer
from products.serializers import ProductPublicSerializer
from subscriptions.serializers import PlanSummarySerializer
from subscriptions.services import check_minimum_quantity

from .models import Quotation, QuotationItem, QuotationTemplate, QuotationTemplateItem


LINE_LIMITS = {
    'quantity': {'min_value': 1},
    'unit_price': {'min_value': 0},
    'tax_rate': {'min_value': 0, 'max_value': 100},
}


class QuotationItemSerializer(serializers.ModelSerializer):
    product_detail = ProductPublicSerializer(source='product', read_only=True)
    line_subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    line_tax = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = QuotationItem
        fields = (
            'id',
            'product',
            'product_detail',
            'variant',
            'quantity',
            'unit_price',
            'tax_rate',
            'line_subtotal',
            'line_tax',
            'line_total',
        )
        read_only_fields = ('id',)
        extra_kwargs = LINE_LIMITS


class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True)
    customer_detail = UserSerializer(source='customer', read_only=True)
    plan_detail = PlanSummarySerializer(source='plan', read_only=True)
    valid_until = serializers.DateField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    tax_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Quotation
        fields = (
            'id',
            'customer',
            'customer_detail',
            'plan',
            'plan_detail',
            'status',
            'validity_days',
            'payment_terms',
            'issued_date',
            'valid_until',
            'is_expired',
            'notes',
            'items',
            'subtotal',
            'tax_total',
            'total',
            'subscription',
            'created_by',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'status', 'issued_date', 'subscription', 'created_by', 'created_at', 'updated_at')
        extra_kwargs = {'validity_days': {'min_value': 1}}

    def validate_customer(self, value):
        if value.role != User.Role.CUSTOMER:
            raise serializers.ValidationError('Quotations can only be created for customer accounts.')
        return value

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('A quotation needs at least one item.')
        return value

    def validate(self, attrs):
        plan = attrs.get('plan', getattr(self.instance, 'plan', None))
        items = attrs.get('items')
        if plan is not None:
            if not plan.is_active:
                raise serializers.ValidationError({'plan': 'This plan is switched off and cannot be quoted.'})
            if items is not None:
                check_minimum_quantity(plan, items)
        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        quotation = Quotation.objects.create(**validated_data)
        for item_data in items_data:
            QuotationItem.objects.create(quotation=quotation, **item_data)
        return quotation

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                QuotationItem.objects.create(quotation=instance, **item_data)
        return instance


class QuotationTemplateItemSerializer(serializers.ModelSerializer):
    product_detail = ProductPublicSerializer(source='product', read_only=True)

    class Meta:
        model = QuotationTemplateItem
        fields = ('id', 'product', 'product_detail', 'variant', 'quantity', 'unit_price', 'tax_rate')
        read_only_fields = ('id',)
        extra_kwargs = LINE_LIMITS


class QuotationTemplateSerializer(serializers.ModelSerializer):
    items = QuotationTemplateItemSerializer(many=True)
    plan_detail = PlanSummarySerializer(source='plan', read_only=True)

    class Meta:
        model = QuotationTemplate
        fields = ('id', 'name', 'plan', 'plan_detail', 'notes', 'items', 'created_by', 'created_at')
        read_only_fields = ('id', 'created_by', 'created_at')

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('A template needs at least one item.')
        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        template = QuotationTemplate.objects.create(**validated_data)
        for item_data in items_data:
            QuotationTemplateItem.objects.create(template=template, **item_data)
        return template

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                QuotationTemplateItem.objects.create(template=instance, **item_data)
        return instance
