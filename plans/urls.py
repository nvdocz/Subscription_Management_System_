from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import CatalogPlanListView, PlanRequestView, SubscriptionPlanViewSet

router = DefaultRouter()
router.register('plans', SubscriptionPlanViewSet, basename='plan')

urlpatterns = router.urls + [
    path('catalog/plans/', CatalogPlanListView.as_view(), name='catalog-plans'),
    path('catalog/plans/<int:pk>/request/', PlanRequestView.as_view(), name='catalog-plan-request'),
]
