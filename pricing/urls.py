from rest_framework.routers import DefaultRouter

from .views import DiscountViewSet, TaxRuleViewSet

router = DefaultRouter()
router.register('tax-rules', TaxRuleViewSet, basename='tax-rule')
router.register('discounts', DiscountViewSet, basename='discount')

urlpatterns = router.urls
