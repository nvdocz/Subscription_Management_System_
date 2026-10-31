from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from config.money import r2
from accounts.serializers import UserSerializer
from plans.models import SubscriptionPlan
from pricing.models import tax_rate_for

from . import services
from .models import Subscription, SubscriptionEvent, SubscriptionLine



class PlanSummarySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = (
            'id', 'name', 'price', 'billing_frequency', 'product', 'product_name', 'min_quantity',
            'allow_pause', 'allow_early_closure', 'allow_renewal', 'auto_close_enabled',
        )
        read_only_fields = fields


class SubscriptionLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True, default=None)
    effective_tax_rate = serializers.SerializerMethodField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SubscriptionLine
        fields = (
            'id', 'product', 'product_name', 'variant', 'variant_name', 'quantity', 'unit_price',
            'tax_rate', 'effective_tax_rate', 'amount',
        )
        read_only_fields = ('id',)
        extra_kwargs = {
            'quantity': {'min_value': 1},
            'unit_price': {'min_value': 0},
            'tax_rate': {'min_value': 0, 'max_value': 100},
        }

    def get_effective_tax_rate(self, line):
        return line.tax_rate if line.tax_rate is not None else tax_rate_for(line.product)


class SubscriptionEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True, default=None)

    class Meta:
        model = SubscriptionEvent
        fields = ('id', 'message', 'from_status', 'to_status', 'actor_name', 'created_at')
        read_only_fields = fields


class SubscriptionListSerializer(serializers.ModelSerializer):
    customer_detail = UserSerializer(source='customer', read_only=True)
    plan_detail = PlanSummarySerializer(source='plan', read_only=True)
    allowed_actions = serializers.SerializerMethodField()
    cycle_subtotal = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = (
            'id', 'number', 'customer', 'customer_detail', 'plan', 'plan_detail', 'status', 'payment_terms',
            'start_date', 'expiry_date', 'end_date', 'next_billing_date', 'cycle_subtotal', 'allowed_actions',
            'created_at',
        )
        read_only_fields = fields

    def get_allowed_actions(self, subscription):
        return services.allowed_actions(subscription, self.context['request'].user)

    def get_cycle_subtotal(self, subscription):
        annotated = getattr(subscription, 'cycle_total', None)
        return annotated if annotated is not None else subscription.cycle_subtotal


class SubscriptionDetailSerializer(SubscriptionListSerializer):
    lines = SubscriptionLineSerializer(many=True)
    events = SubscriptionEventSerializer(many=True, read_only=True)
    estimated_tax = serializers.SerializerMethodField()
    estimated_total = serializers.SerializerMethodField()

    class Meta(SubscriptionListSerializer.Meta):
        fields = SubscriptionListSerializer.Meta.fields + ('lines', 'events', 'estimated_tax', 'estimated_total')
        read_only_fields = (
            'id', 'number', 'status', 'end_date', 'next_billing_date', 'cycle_subtotal', 'allowed_actions',
            'created_at', 'customer_detail', 'plan_detail', 'events', 'estimated_tax', 'estimated_total',
        )

    def get_estimated_tax(self, subscription):
        total = Decimal('0.00')
        for line in subscription.lines.select_related('product'):
            rate = line.tax_rate if line.tax_rate is not None else tax_rate_for(line.product)
            total += r2(line.amount * rate / Decimal('100'))
        return total

    def get_estimated_total(self, subscription):
        return subscription.cycle_subtotal + self.get_estimated_tax(subscription)

    def validate_customer(self, value):
        if value.role != User.Role.CUSTOMER:
            raise serializers.ValidationError('Subscriptions can only be created for customer accounts.')
        return value

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError('Add at least one product line.')
        return value

    def validate(self, attrs):
        plan = attrs.get('plan', getattr(self.instance, 'plan', None))
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        expiry = attrs.get('expiry_date', getattr(self.instance, 'expiry_date', None))
        if plan is not None:
            today = timezone.localdate()
            if not plan.is_active:
                raise serializers.ValidationError({'plan': 'This plan is switched off and cannot be sold.'})
            if plan.end_date and plan.end_date < today:
                raise serializers.ValidationError({'plan': 'This plan is no longer available.'})
            if start and plan.start_date > start and plan.start_date > today:
                raise serializers.ValidationError({'start_date': f'This plan is available from {plan.start_date}.'})
            if start and plan.end_date and start > plan.end_date:
                raise serializers.ValidationError({'start_date': f'This plan ends on {plan.end_date}.'})
        if start and expiry and expiry < start:
            raise serializers.ValidationError({'expiry_date': 'Expiry date cannot be before the start date.'})
        lines = attrs.get('lines')
        if plan is not None and lines is not None:
            services.check_minimum_quantity(plan, lines)
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop('lines')
        validated_data.setdefault('expiry_date', services.default_expiry(validated_data['plan'], validated_data['start_date']))
        subscription = Subscription.objects.create(**validated_data)
        services.create_lines(subscription, lines)
        subscription.log('Subscription created', validated_data.get('created_by'), to_status=subscription.status)
        return subscription

    def update(self, instance, validated_data):
        lines = validated_data.pop('lines', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            services.create_lines(instance, lines)
        return instance
