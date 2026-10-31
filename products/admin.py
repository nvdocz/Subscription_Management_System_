from django.contrib import admin

from .models import Product, ProductVariant


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_type', 'sales_price', 'cost_price', 'is_archived')
    list_filter = ('product_type', 'is_archived')
    search_fields = ('name',)
    inlines = [ProductVariantInline]
