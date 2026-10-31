"""Who may do what: every endpoint against every role, plus the rules that keep customer data private."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from billing.engine import build_invoice
from billing.models import Invoice
from plans.models import SubscriptionPlan
from pricing.models import Discount, TaxRule
from products.models import Product, ProductVariant
from quotations.models import Quotation, QuotationItem
from subscriptions import services
from subscriptions.models import Subscription, SubscriptionLine

TODAY = timezone.localdate()
ANON, CUSTOMER, STAFF, ADMIN = 'anon', 'customer', 'staff', 'admin'

# (method, url, roles that are allowed in). Everyone else must be refused with 401/403.
ENDPOINTS = [
    ('get', '/api/auth/me/', {CUSTOMER, STAFF, ADMIN}),
    ('get', '/api/auth/users/', {STAFF, ADMIN}),
    ('post', '/api/auth/users/', {STAFF, ADMIN}),
    ('get', '/api/products/', {ADMIN}),
    ('post', '/api/products/', {ADMIN}),
    ('get', '/api/catalog/products/', {STAFF, ADMIN}),
    ('get', '/api/plans/', {ADMIN}),
    ('post', '/api/plans/', {ADMIN}),
    ('get', '/api/catalog/plans/', {CUSTOMER, STAFF, ADMIN}),
    ('get', '/api/tax-rules/', {STAFF, ADMIN}),
    ('post', '/api/tax-rules/', {ADMIN}),
    ('get', '/api/discounts/', {STAFF, ADMIN}),
    ('post', '/api/discounts/', {ADMIN}),
    ('get', '/api/quotations/', {CUSTOMER, STAFF, ADMIN}),
    ('post', '/api/quotations/', {STAFF, ADMIN}),
    ('get', '/api/quotation-templates/', {STAFF, ADMIN}),
    ('post', '/api/quotation-templates/', {STAFF, ADMIN}),
    ('get', '/api/subscriptions/', {CUSTOMER, STAFF, ADMIN}),
    ('post', '/api/subscriptions/', {STAFF, ADMIN}),
    ('get', '/api/invoices/', {CUSTOMER, STAFF, ADMIN}),
    ('post', '/api/invoices/confirm-drafts/', {STAFF, ADMIN}),
    ('get', '/api/payments/', {CUSTOMER, STAFF, ADMIN}),
    ('post', '/api/payments/', {STAFF, ADMIN}),
    ('get', '/api/billing/preview/', {STAFF, ADMIN}),
    ('post', '/api/billing/run/', {STAFF, ADMIN}),
    ('get', '/api/dashboard/admin/', {ADMIN}),
    ('get', '/api/dashboard/staff/', {STAFF}),
    ('get', '/api/dashboard/customer/', {CUSTOMER}),
    ('get', '/api/dashboard/reports/', {STAFF, ADMIN}),
    ('get', '/api/search/?q=al', {CUSTOMER, STAFF, ADMIN}),
]


class AccessTestCase(APITestCase):
    def setUp(self):
        self.users = {
            ADMIN: User.objects.create_user('boss', 'boss@example.com', 'Boss#Pass123', role='admin'),
            STAFF: User.objects.create_user('rep', 'rep@example.com', 'Rep#Pass1234', role='staff'),
            CUSTOMER: User.objects.create_user('alice', 'alice@example.com', 'Alice#Pass12', role='customer'),
        }
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'Bob#Pass1234', role='customer')
        self.alice = self.users[CUSTOMER]
        self.product = Product.objects.create(
            name='CRM', product_type='service', sales_price=1000, cost_price=Decimal('412.50'), notes='margin-secret-note'
        )
        ProductVariant.objects.create(product=self.product, name='Odoo', extra_price=560)
        self.plan = SubscriptionPlan.objects.create(
            product=self.product, name='Monthly', price=1000, billing_frequency='monthly', start_date=TODAY - timedelta(days=30)
        )
        TaxRule.objects.create(name='GST', rate=18)
        Discount.objects.create(name='Promo', kind='fixed', value=50, start_date=TODAY - timedelta(days=1))

    def client_for(self, role):
        client = APIClient()
        if role != ANON:
            client.force_authenticate(self.users[role])
        return client

    def subscribe(self, customer, status_after='active'):
        subscription = Subscription.objects.create(
            customer=customer, plan=self.plan, start_date=TODAY, expiry_date=TODAY + timedelta(days=365)
        )
        SubscriptionLine.objects.create(
            subscription=subscription, product=self.product, quantity=1, unit_price=self.plan.price
        )
        if status_after == 'active':
            services.confirm(subscription, self.users[STAFF])
        subscription.refresh_from_db()
        return subscription

    def quotation(self, customer, status):
        quotation = Quotation.objects.create(customer=customer, plan=self.plan, status=status, created_by=self.users[STAFF])
        QuotationItem.objects.create(quotation=quotation, product=self.product, quantity=1, unit_price=1000, tax_rate=18)
        return quotation


class PermissionMatrixTests(AccessTestCase):
    def test_every_endpoint_is_open_only_to_the_roles_that_need_it(self):
        failures = []
        for method, url, allowed in ENDPOINTS:
            for role in (ANON, CUSTOMER, STAFF, ADMIN):
                response = getattr(self.client_for(role), method)(url, {}, format='json')
                refused = response.status_code in (401, 403)
                should_refuse = role not in allowed
                if refused != should_refuse:
                    failures.append(f'{role:8} {method.upper():4} {url} -> {response.status_code} (expected {"refusal" if should_refuse else "access"})')
                if role == ANON and response.status_code != 401:
                    failures.append(f'anon     {method.upper():4} {url} -> {response.status_code} (expected 401)')
        self.assertEqual(failures, [], '\n' + '\n'.join(failures))


class PrivacyTests(AccessTestCase):
    def setUp(self):
        super().setUp()
        self.subscription = self.subscribe(self.alice)
        self.invoice = self.subscription.invoices.get()
        self.sent = self.quotation(self.alice, 'sent')
        self.draft_quotation = self.quotation(self.alice, 'draft')
        self.draft_subscription = self.subscribe(self.alice, status_after='draft')
        self.draft_invoice = build_invoice(self.subscription, self.subscription.next_billing_date, confirm=False)
        self.cancelled_invoice = build_invoice(
            self.subscription, self.subscription.next_billing_date + timedelta(days=40), confirm=False
        )
        Invoice.objects.filter(pk=self.cancelled_invoice.pk).update(status='cancelled')

    CUSTOMER_FACING = [
        '/api/quotations/', '/api/subscriptions/', '/api/invoices/', '/api/payments/', '/api/catalog/plans/',
        '/api/dashboard/customer/', '/api/search/?q=al',
    ]

    def test_cost_price_and_internal_notes_never_reach_customers_or_staff(self):
        for role in (CUSTOMER, STAFF):
            client = self.client_for(role)
            urls = list(self.CUSTOMER_FACING)
            if role == STAFF:
                urls = [u for u in urls if 'customer' not in u] + ['/api/catalog/products/', '/api/dashboard/staff/', '/api/quotation-templates/']
            urls += [f'/api/quotations/{self.sent.id}/', f'/api/subscriptions/{self.subscription.id}/', f'/api/invoices/{self.invoice.id}/']
            for url in urls:
                body = client.get(url).content.decode()
                self.assertNotIn('cost_price', body, f'{role} can read cost_price at {url}')
                self.assertNotIn('412.5', body, f'{role} can read the cost at {url}')
                self.assertNotIn('margin-secret-note', body, f'{role} can read product notes at {url}')

    def test_admin_still_manages_cost_price(self):
        body = self.client_for(ADMIN).get('/api/products/').content.decode()
        self.assertIn('cost_price', body)

    def test_customers_do_not_see_unsent_or_void_documents(self):
        client = self.client_for(CUSTOMER)
        quotation_ids = {q['id'] for q in client.get('/api/quotations/').json()}
        self.assertIn(self.sent.id, quotation_ids)
        self.assertNotIn(self.draft_quotation.id, quotation_ids)
        subscription_ids = {s['id'] for s in client.get('/api/subscriptions/').json()['results']}
        self.assertIn(self.subscription.id, subscription_ids)
        self.assertNotIn(self.draft_subscription.id, subscription_ids)
        invoice_ids = {i['id'] for i in client.get('/api/invoices/').json()['results']}
        self.assertIn(self.invoice.id, invoice_ids)
        self.assertNotIn(self.draft_invoice.id, invoice_ids)
        self.assertNotIn(self.cancelled_invoice.id, invoice_ids)
        for url in (
            f'/api/quotations/{self.draft_quotation.id}/',
            f'/api/subscriptions/{self.draft_subscription.id}/',
            f'/api/invoices/{self.draft_invoice.id}/',
            f'/api/invoices/{self.cancelled_invoice.id}/',
        ):
            self.assertEqual(client.get(url).status_code, 404, url)

    def test_staff_still_see_drafts(self):
        client = self.client_for(STAFF)
        self.assertIn(self.draft_invoice.id, {i['id'] for i in client.get('/api/invoices/').json()['results']})
        self.assertIn(self.draft_quotation.id, {q['id'] for q in client.get('/api/quotations/').json()})

    def test_a_customer_cannot_read_or_act_on_someone_elses_records(self):
        client = self.client_for(CUSTOMER)
        theirs = self.subscribe(self.bob)
        their_invoice = theirs.invoices.get()
        their_quotation = self.quotation(self.bob, 'sent')
        for method, url in (
            ('get', f'/api/subscriptions/{theirs.id}/'),
            ('post', f'/api/subscriptions/{theirs.id}/do/pause/'),
            ('post', f'/api/subscriptions/{theirs.id}/do/close/'),
            ('get', f'/api/invoices/{their_invoice.id}/'),
            ('post', f'/api/invoices/{their_invoice.id}/pay/'),
            ('get', f'/api/quotations/{their_quotation.id}/'),
            ('post', f'/api/quotations/{their_quotation.id}/accept/'),
        ):
            self.assertEqual(getattr(client, method)(url).status_code, 404, f'{method} {url}')
        their_invoice.refresh_from_db()
        self.assertEqual(their_invoice.status, 'confirmed')

    def test_customer_lists_hold_only_their_own_rows(self):
        self.subscribe(self.bob)
        client = self.client_for(CUSTOMER)
        for url, key in (('/api/subscriptions/', 'customer'), ('/api/invoices/', 'customer')):
            rows = client.get(url).json()['results']
            self.assertTrue(rows)
            self.assertEqual({r[key] for r in rows}, {self.alice.id}, url)

    def test_staff_cannot_create_staff_or_admin_accounts(self):
        client = self.client_for(STAFF)
        for role in ('staff', 'admin'):
            payload = {'username': f'x{role}', 'email': f'x{role}@example.com', 'password': 'Valid#Pass1', 'role': role}
            self.assertEqual(client.post('/api/auth/users/', payload, format='json').status_code, 400, role)

    def test_staff_cannot_change_roles_and_admin_cannot_change_their_own(self):
        self.assertEqual(
            self.client_for(STAFF).patch(f'/api/auth/users/{self.alice.id}/role/', {'role': 'admin'}, format='json').status_code, 403
        )
        own = self.client_for(ADMIN).patch(f'/api/auth/users/{self.users[ADMIN].id}/role/', {'role': 'customer'}, format='json')
        self.assertEqual(own.status_code, 400)
        self.users[ADMIN].refresh_from_db()
        self.assertEqual(self.users[ADMIN].role, 'admin')
        other = self.client_for(ADMIN).patch(f'/api/auth/users/{self.bob.id}/role/', {'role': 'staff'}, format='json')
        self.assertEqual(other.status_code, 200)

    def test_products_and_plans_in_use_cannot_be_deleted_and_fail_cleanly(self):
        admin = self.client_for(ADMIN)
        product = admin.delete(f'/api/products/{self.product.id}/')
        plan = admin.delete(f'/api/plans/{self.plan.id}/')
        self.assertEqual(product.status_code, 400, product.content)
        self.assertEqual(plan.status_code, 400, plan.content)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertTrue(SubscriptionPlan.objects.filter(pk=self.plan.pk).exists())
