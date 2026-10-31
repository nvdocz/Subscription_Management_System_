from rest_framework.routers import DefaultRouter

from .views import QuotationTemplateViewSet, QuotationViewSet

router = DefaultRouter()
router.register('quotations', QuotationViewSet, basename='quotation')
router.register('quotation-templates', QuotationTemplateViewSet, basename='quotation-template')

urlpatterns = router.urls
