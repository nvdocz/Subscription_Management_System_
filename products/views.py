from django.db.models import ProtectedError
from rest_framework import generics, serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsAdmin, IsAdminOrStaff

from .models import Product, ProductVariant
from .serializers import ProductSerializer, ProductVariantSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().prefetch_related('variants')
    serializer_class = ProductSerializer
    permission_classes = [IsAdmin]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                'This product is used by subscriptions and cannot be deleted. Archive it to stop selling it.'
            ) from None

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        product = self.get_object()
        product.is_archived = True
        product.save(update_fields=['is_archived'])
        return Response(self.get_serializer(product).data)

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        product = self.get_object()
        product.is_archived = False
        product.save(update_fields=['is_archived'])
        return Response(self.get_serializer(product).data)


class ProductVariantViewSet(viewsets.ModelViewSet):
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return ProductVariant.objects.filter(product_id=self.kwargs['product_pk'])

    def perform_create(self, serializer):
        serializer.save(product_id=self.kwargs['product_pk'])


class CatalogVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ('id', 'name', 'extra_price')


class CatalogProductSerializer(serializers.ModelSerializer):
    variants = CatalogVariantSerializer(many=True, read_only=True)
    default_tax_rate = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ('id', 'name', 'product_type', 'sales_price', 'description', 'variants', 'default_tax_rate')

    def get_default_tax_rate(self, product):
        from pricing.models import tax_rate_for

        return tax_rate_for(product)


class CatalogProductListView(generics.ListAPIView):
    """Sellable products for the internal team. Unlike /products/ it never exposes cost price or notes."""

    serializer_class = CatalogProductSerializer
    permission_classes = [IsAdminOrStaff]

    def get_queryset(self):
        return Product.objects.filter(is_archived=False).prefetch_related('variants')
