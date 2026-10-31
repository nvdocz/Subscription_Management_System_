from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BillingPreviewView, BillingRunView, InvoiceViewSet, PaymentViewSet

router = DefaultRouter()
router.register('invoices', InvoiceViewSet, basename='invoice')
router.register('payments', PaymentViewSet, basename='payment')

urlpatterns = router.urls + [
    path('billing/preview/', BillingPreviewView.as_view(), name='billing-preview'),
    path('billing/run/', BillingRunView.as_view(), name='billing-run'),
]
