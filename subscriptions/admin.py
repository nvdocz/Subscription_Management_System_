from django.contrib import admin

from .models import Subscription, SubscriptionLine


class SubscriptionLineInline(admin.TabularInline):
    model = SubscriptionLine
    extra = 0


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('number', 'customer', 'plan', 'status', 'start_date', 'expiry_date')
    list_filter = ('status',)
    inlines = [SubscriptionLineInline]
