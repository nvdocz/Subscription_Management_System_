from django.contrib import admin

from .models import SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'product', 'price', 'billing_frequency', 'is_active', 'start_date', 'end_date')
    list_filter = ('billing_frequency', 'is_active')
    search_fields = ('name', 'product__name')
