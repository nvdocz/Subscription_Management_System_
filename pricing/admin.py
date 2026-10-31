from django.contrib import admin

from .models import Discount, TaxRule

admin.site.register(TaxRule)
admin.site.register(Discount)
