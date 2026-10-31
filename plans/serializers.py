from rest_framework import serializers

from products.models import Product
from products.serializers import ProductSerializer

from .models import SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    product_detail = ProductSerializer(source='product', read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = SubscriptionPlan
        fields = (
            'id',
            'product',
            'product_detail',
            'name',
            'price',
            'billing_frequency',
            'min_quantity',
            'start_date',
            'end_date',
            'auto_close_enabled',
            'allow_early_closure',
            'allow_pause',
            'allow_renewal',
            'is_active',
            'created_by',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'is_active', 'created_by', 'created_at', 'updated_at')
        extra_kwargs = {'price': {'min_value': 0}, 'min_quantity': {'min_value': 1}}

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if end_date and start_date and end_date < start_date:
            raise serializers.ValidationError({'end_date': 'End date cannot be before the start date.'})
        return attrs


class CatalogPlanSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_description = serializers.CharField(source='product.description', read_only=True)
    relation = serializers.SerializerMethodField()
    requested = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = (
            'id', 'name', 'price', 'billing_frequency', 'min_quantity', 'allow_pause', 'allow_early_closure',
            'allow_renewal', 'auto_close_enabled', 'start_date', 'end_date', 'product', 'product_name',
            'product_description', 'relation', 'requested',
        )
        read_only_fields = fields

    def get_relation(self, plan):
        active_by_product = self.context.get('active_by_product')
        if active_by_product is None:
            return None
        current = active_by_product.get(plan.product_id)
        if current is None:
            return 'subscribe'
        if current.pk == plan.pk:
            return 'current'
        return 'upgrade' if plan.price > current.price else 'downgrade'

    def get_requested(self, plan):
        return plan.pk in self.context.get('requested_plan_ids', set())
