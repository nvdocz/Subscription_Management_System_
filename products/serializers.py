from rest_framework import serializers

from .models import Product, ProductVariant


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ('id', 'product', 'name', 'extra_price', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')
        extra_kwargs = {'product': {'required': False}, 'extra_price': {'min_value': 0}}


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    default_tax_rate = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'product_type',
            'sales_price',
            'cost_price',
            'description',
            'notes',
            'is_archived',
            'created_by',
            'variants',
            'default_tax_rate',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'is_archived', 'created_by', 'created_at', 'updated_at')
        extra_kwargs = {'sales_price': {'min_value': 0}, 'cost_price': {'min_value': 0}}

    def get_default_tax_rate(self, product):
        from pricing.models import tax_rate_for

        return tax_rate_for(product)


class ProductPublicSerializer(serializers.ModelSerializer):
    """What customers and staff may see about a product: never cost price or internal notes."""

    class Meta:
        model = Product
        fields = ('id', 'name', 'product_type', 'description')
        read_only_fields = fields
