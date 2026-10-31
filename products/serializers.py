from rest_framework import serializers

from .models import Product, ProductVariant


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ('id', 'product', 'name', 'extra_price', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')
        extra_kwargs = {'product': {'required': False}}


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)

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
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'is_archived', 'created_by', 'created_at', 'updated_at')
