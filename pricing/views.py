from rest_framework import viewsets

from accounts.permissions import AdminWriteStaffRead

from .models import Discount, TaxRule
from .serializers import DiscountSerializer, TaxRuleSerializer


class TaxRuleViewSet(viewsets.ModelViewSet):
    queryset = TaxRule.objects.select_related('product')
    serializer_class = TaxRuleSerializer
    permission_classes = [AdminWriteStaffRead]


class DiscountViewSet(viewsets.ModelViewSet):
    queryset = Discount.objects.prefetch_related('products')
    serializer_class = DiscountSerializer
    permission_classes = [AdminWriteStaffRead]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
