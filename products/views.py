from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsAdmin

from .models import Product, ProductVariant
from .serializers import ProductSerializer, ProductVariantSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().prefetch_related('variants')
    serializer_class = ProductSerializer
    permission_classes = [IsAdmin]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

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
