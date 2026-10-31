from django.db import migrations


def upgrade(apps, schema_editor):
    Invoice = apps.get_model('billing', 'Invoice')
    Line = apps.get_model('billing', 'InvoiceLine')

    for invoice in Invoice.objects.all():
        if invoice.status == 'pending':
            invoice.status = 'confirmed'
        invoice.subtotal = invoice.amount
        invoice.save(update_fields=['status', 'subtotal'])
        if not Line.objects.filter(invoice=invoice).exists():
            Line.objects.create(
                invoice=invoice,
                description='Subscription charge',
                quantity=1,
                unit_price=invoice.amount,
                tax_rate=0,
            )


class Migration(migrations.Migration):
    dependencies = [('billing', '0003_invoicediscount_discount_invoicediscount_invoice_and_more')]

    operations = [migrations.RunPython(upgrade, migrations.RunPython.noop)]
