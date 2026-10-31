from django.core.management.base import BaseCommand

from billing.engine import run_billing


class Command(BaseCommand):
    help = 'Generate invoices for every subscription that is due. Safe to run repeatedly: nothing is billed twice.'

    def add_arguments(self, parser):
        parser.add_argument('--confirm', action='store_true', help='Confirm the generated invoices straight away.')

    def handle(self, *args, **options):
        result = run_billing(confirm=options['confirm'])
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {result['invoices_created']} invoice(s) totalling {result['total_billed']}; "
                f"activated {result['activated']}, auto-closed {result['auto_closed']}."
            )
        )
