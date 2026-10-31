from django.contrib import admin

from .models import Quotation, QuotationItem, QuotationTemplate, QuotationTemplateItem


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 0


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'plan', 'status', 'issued_date', 'validity_days')
    list_filter = ('status',)
    inlines = [QuotationItemInline]


class QuotationTemplateItemInline(admin.TabularInline):
    model = QuotationTemplateItem
    extra = 0


@admin.register(QuotationTemplate)
class QuotationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan')
    inlines = [QuotationTemplateItemInline]
