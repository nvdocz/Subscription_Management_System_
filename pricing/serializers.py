from rest_framework import serializers

from .models import Discount, TaxRule


class TaxRuleSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)
    scope = serializers.CharField(read_only=True)

    class Meta:
        model = TaxRule
        fields = ('id', 'name', 'rate', 'product_type', 'product', 'product_name', 'scope', 'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')

    def validate(self, attrs):
        if attrs.get('product') and attrs.get('product_type'):
            raise serializers.ValidationError('Choose either a specific product or a product type, not both.')
        if attrs.get('rate') is not None and not 0 <= attrs['rate'] <= 100:
            raise serializers.ValidationError({'rate': 'Rate must be between 0 and 100.'})
        return attrs


class DiscountSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    product_names = serializers.SerializerMethodField()

    class Meta:
        model = Discount
        fields = (
            'id', 'name', 'kind', 'value', 'applies_to', 'products', 'product_names', 'min_purchase',
            'min_quantity', 'start_date', 'end_date', 'usage_limit', 'times_used', 'is_active', 'status', 'created_at',
        )
        read_only_fields = ('id', 'times_used', 'created_at')
        extra_kwargs = {'min_purchase': {'min_value': 0}, 'usage_limit': {'min_value': 1}}

    def get_product_names(self, discount):
        return [p.name for p in discount.products.all()]

    def validate(self, attrs):
        kind = attrs.get('kind', getattr(self.instance, 'kind', None))
        value = attrs.get('value', getattr(self.instance, 'value', None))
        if kind == Discount.Kind.PERCENTAGE and value is not None and not 0 < value <= 100:
            raise serializers.ValidationError({'value': 'A percentage discount must be between 0 and 100.'})
        if value is not None and value <= 0:
            raise serializers.ValidationError({'value': 'Value must be greater than zero.'})
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'End date cannot be before the start date.'})
        applies_to = attrs.get('applies_to', getattr(self.instance, 'applies_to', None))
        products = attrs.get('products')
        if products is None and self.instance is not None:
            products = list(self.instance.products.all())
        if applies_to == Discount.AppliesTo.PRODUCTS and not products:
            raise serializers.ValidationError({'products': 'Pick at least one product for a product discount.'})
        return attrs
