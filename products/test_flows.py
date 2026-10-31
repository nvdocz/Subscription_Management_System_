"""PDF story: launching a new plan. Products, variants, billing frequencies, availability dates."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from plans.models import SubscriptionPlan
from pricing.models import TaxRule
from products.models import Product, ProductVariant

FAST = dict(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
TODAY = timezone.localdate()


@override_settings(**FAST)
class LaunchAProductTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('boss', 'boss@example.com', 'Boss#Pass123', role='admin')
        self.staff = User.objects.create_user('rep', 'rep@example.com', 'Rep#Pass1234', role='staff')
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'Alice#Pass12', role='customer')

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def new_product(self, **overrides):
        payload = {
            'name': 'Billing Suite',
            'product_type': 'service',
            'sales_price': '1000.00',
            'cost_price': '400.00',
            'description': 'Cloud billing',
            'notes': 'internal margin note',
        }
        payload.update(overrides)
        return self.as_user(self.admin).post('/api/products/', payload, format='json')

    def new_plan(self, product, **overrides):
        values = dict(
            product=product, name='Monthly', price=Decimal('1000.00'), billing_frequency='monthly',
            start_date=TODAY - timedelta(days=30),
        )
        values.update(overrides)
        return SubscriptionPlan.objects.create(**values)

    def subscription_payload(self, product, plan, **overrides):
        payload = {
            'customer': self.alice.id,
            'plan': plan.id,
            'start_date': str(TODAY),
            'lines': [{'product': product.id, 'quantity': 1, 'unit_price': '1000.00'}],
        }
        payload.update(overrides)
        return payload

    # ------------------------------------------------------------------ products and variants

    def test_admin_creates_a_product_with_name_type_prices_and_notes(self):
        response = self.new_product()
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body['name'], 'Billing Suite')
        self.assertEqual(body['product_type'], 'service')
        self.assertEqual(body['sales_price'], '1000.00')
        self.assertEqual(body['cost_price'], '400.00')
        self.assertEqual(body['notes'], 'internal margin note')
        self.assertEqual(body['created_by'], self.admin.id)
        self.assertFalse(body['is_archived'])

    def test_only_the_admin_can_create_or_change_products(self):
        payload = {'name': 'X', 'product_type': 'goods', 'sales_price': '1', 'cost_price': '1'}
        for user in (self.staff, self.alice):
            self.assertEqual(self.as_user(user).post('/api/products/', payload, format='json').status_code, 403)
        product = Product.objects.create(name='P', product_type='goods', sales_price=1, cost_price=1)
        self.assertEqual(self.as_user(self.staff).patch(f'/api/products/{product.id}/', {'name': 'Hacked'}, format='json').status_code, 403)
        self.assertEqual(self.as_user(self.staff).delete(f'/api/products/{product.id}/').status_code, 403)

    def test_product_type_must_be_goods_or_service(self):
        self.assertEqual(self.new_product(product_type='magic').status_code, 400)

    def test_a_variant_adds_to_the_price_and_staff_see_it_without_cost(self):
        product_id = self.new_product().json()['id']
        variant = self.as_user(self.admin).post(
            f'/api/products/{product_id}/variants/', {'name': 'Odoo', 'extra_price': '560.00'}, format='json'
        )
        self.assertEqual(variant.status_code, 201, variant.content)
        catalog = self.as_user(self.staff).get('/api/catalog/products/')
        self.assertEqual(catalog.status_code, 200)
        row = next(p for p in catalog.json() if p['id'] == product_id)
        self.assertEqual(row['sales_price'], '1000.00')
        self.assertEqual([(v['name'], v['extra_price']) for v in row['variants']], [('Odoo', '560.00')])
        body = catalog.content.decode()
        self.assertNotIn('cost_price', body)
        self.assertNotIn('internal margin note', body)

    def test_only_admin_manages_variants(self):
        product_id = self.new_product().json()['id']
        url = f'/api/products/{product_id}/variants/'
        self.assertEqual(self.as_user(self.staff).post(url, {'name': 'X', 'extra_price': '1'}, format='json').status_code, 403)
        variant = self.as_user(self.admin).post(url, {'name': 'Odoo', 'extra_price': '560'}, format='json').json()
        self.assertEqual(self.as_user(self.admin).delete(f'{url}{variant["id"]}/').status_code, 204)

    def test_archived_products_leave_the_sales_catalogue_and_can_return(self):
        product_id = self.new_product().json()['id']
        admin, staff = self.as_user(self.admin), self.as_user(self.staff)
        self.assertEqual(admin.post(f'/api/products/{product_id}/archive/').json()['is_archived'], True)
        self.assertNotIn(product_id, [p['id'] for p in staff.get('/api/catalog/products/').json()])
        admin.post(f'/api/products/{product_id}/unarchive/')
        self.assertIn(product_id, [p['id'] for p in staff.get('/api/catalog/products/').json()])

    def test_the_variant_price_flows_through_to_the_invoice_line(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        variant = ProductVariant.objects.create(product=product, name='Odoo', extra_price=560)
        plan = self.new_plan(product)
        staff = self.as_user(self.staff)
        unit_price = product.sales_price + variant.extra_price
        payload = self.subscription_payload(product, plan, lines=[
            {'product': product.id, 'variant': variant.id, 'quantity': 1, 'unit_price': str(unit_price)}
        ])
        created = staff.post('/api/subscriptions/', payload, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        line = created.json()['lines'][0]
        self.assertEqual(line['unit_price'], '1560.00')
        self.assertEqual(line['variant_name'], 'Odoo')
        subscription_id = created.json()['id']
        self.assertEqual(staff.post(f'/api/subscriptions/{subscription_id}/do/confirm/').json()['status'], 'active')
        invoice = staff.get(f'/api/invoices/?subscription={subscription_id}').json()['results'][0]
        detail = staff.get(f'/api/invoices/{invoice["id"]}/').json()
        self.assertEqual(detail['lines'][0]['unit_price'], '1560.00')
        self.assertIn('Odoo', detail['lines'][0]['description'])
        self.assertEqual(detail['amount'], '1560.00')

    def test_the_catalogue_shows_the_tax_rate_the_admin_rules_give(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        TaxRule.objects.create(name='GST', rate=18)
        TaxRule.objects.create(name='Services', rate=12, product_type='service')
        row = self.as_user(self.staff).get('/api/catalog/products/').json()[0]
        self.assertEqual(float(row['default_tax_rate']), 12.0)
        TaxRule.objects.create(name='This one', rate=5, product=product)
        row = self.as_user(self.staff).get('/api/catalog/products/').json()[0]
        self.assertEqual(float(row['default_tax_rate']), 5.0)

    # ------------------------------------------------------------------ plans

    def test_every_billing_frequency_can_be_created_through_the_api(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        admin = self.as_user(self.admin)
        for frequency in ('daily', 'weekly', 'monthly', 'quarterly', 'yearly'):
            with self.subTest(frequency=frequency):
                response = admin.post('/api/plans/', {
                    'product': product.id, 'name': f'{frequency} plan', 'price': '99.00', 'billing_frequency': frequency,
                    'min_quantity': 2, 'start_date': str(TODAY),
                }, format='json')
                self.assertEqual(response.status_code, 201, response.content)
                self.assertEqual(response.json()['billing_frequency'], frequency)
                self.assertEqual(response.json()['min_quantity'], 2)
        bad = admin.post('/api/plans/', {
            'product': product.id, 'name': 'x', 'price': '1', 'billing_frequency': 'hourly', 'start_date': str(TODAY),
        }, format='json')
        self.assertEqual(bad.status_code, 400)

    def test_the_lifecycle_options_are_stored_per_plan(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        response = self.as_user(self.admin).post('/api/plans/', {
            'product': product.id, 'name': 'Strict', 'price': '10', 'billing_frequency': 'monthly', 'start_date': str(TODAY),
            'auto_close_enabled': True, 'allow_early_closure': False, 'allow_pause': False, 'allow_renewal': False,
        }, format='json')
        body = response.json()
        self.assertEqual(
            (body['auto_close_enabled'], body['allow_early_closure'], body['allow_pause'], body['allow_renewal']),
            (True, False, False, False),
        )

    def test_next_billing_boundaries_for_each_frequency(self):
        def step(frequency, start):
            return SubscriptionPlan(billing_frequency=frequency).next_billing_after(start)

        cases = [
            ('daily', date(2026, 10, 31), date(2026, 11, 1)),
            ('daily', date(2026, 12, 31), date(2027, 1, 1)),
            ('daily', date(2028, 2, 28), date(2028, 2, 29)),
            ('weekly', date(2026, 10, 31), date(2026, 11, 7)),
            ('weekly', date(2026, 12, 28), date(2027, 1, 4)),
            ('monthly', date(2026, 1, 31), date(2026, 2, 28)),
            ('monthly', date(2028, 1, 31), date(2028, 2, 29)),
            ('monthly', date(2026, 12, 15), date(2027, 1, 15)),
            ('monthly', date(2026, 3, 31), date(2026, 4, 30)),
            ('quarterly', date(2026, 11, 30), date(2027, 2, 28)),
            ('quarterly', date(2026, 10, 1), date(2027, 1, 1)),
            ('yearly', date(2028, 2, 29), date(2029, 2, 28)),
            ('yearly', date(2026, 10, 31), date(2027, 10, 31)),
        ]
        for frequency, start, expected in cases:
            with self.subTest(frequency=frequency, start=str(start)):
                self.assertEqual(step(frequency, start), expected)

    def test_a_month_end_start_does_not_drift_to_the_28th_for_ever(self):
        plan = SubscriptionPlan(billing_frequency='monthly')
        boundary = date(2026, 1, 31)
        seen = [boundary]
        for _ in range(3):
            boundary = plan.next_billing_after(boundary, anchor=date(2026, 1, 31))
            seen.append(boundary)
        self.assertEqual(seen[1], date(2026, 2, 28))
        self.assertEqual(seen[2], date(2026, 3, 31), f'billing dates drifted: {seen}')
        self.assertEqual(seen[3], date(2026, 4, 30))

    def test_plan_dates_must_be_in_order(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        admin = self.as_user(self.admin)
        base = {'product': product.id, 'name': 'P', 'price': '10', 'billing_frequency': 'monthly'}
        backwards = admin.post('/api/plans/', {**base, 'start_date': '2026-11-10', 'end_date': '2026-11-01'}, format='json')
        self.assertEqual(backwards.status_code, 400)
        self.assertIn('end_date', backwards.json())
        same_day = admin.post('/api/plans/', {**base, 'start_date': '2026-11-10', 'end_date': '2026-11-10'}, format='json')
        self.assertEqual(same_day.status_code, 201)

    def test_minimum_quantity_must_be_a_positive_whole_number(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        admin = self.as_user(self.admin)
        base = {'product': product.id, 'name': 'P', 'price': '10', 'billing_frequency': 'monthly', 'start_date': str(TODAY)}
        for quantity in (-1, 'two', 1.5):
            with self.subTest(quantity=quantity):
                self.assertEqual(admin.post('/api/plans/', {**base, 'min_quantity': quantity}, format='json').status_code, 400)
        with self.subTest(quantity=0):
            self.assertEqual(
                admin.post('/api/plans/', {**base, 'min_quantity': 0}, format='json').status_code, 400,
                'a minimum purchase quantity of 0 is accepted',
            )

    def test_prices_cannot_be_negative(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        admin = self.as_user(self.admin)
        with self.subTest(what='product sales price'):
            self.assertEqual(self.new_product(sales_price='-5.00').status_code, 400, 'negative sales price accepted')
        with self.subTest(what='product cost price'):
            self.assertEqual(self.new_product(name='Other', cost_price='-5.00').status_code, 400, 'negative cost price accepted')
        with self.subTest(what='plan price'):
            response = admin.post('/api/plans/', {
                'product': product.id, 'name': 'P', 'price': '-10', 'billing_frequency': 'monthly', 'start_date': str(TODAY),
            }, format='json')
            self.assertEqual(response.status_code, 400, 'negative plan price accepted')

    # ------------------------------------------------------------------ availability

    def test_a_plan_that_has_ended_cannot_be_subscribed_to_or_found_in_the_catalogue(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        ended = self.new_plan(product, name='Ended', start_date=TODAY - timedelta(days=60), end_date=TODAY - timedelta(days=1))
        staff = self.as_user(self.staff)
        refused = staff.post('/api/subscriptions/', self.subscription_payload(product, ended), format='json')
        self.assertEqual(refused.status_code, 400)
        self.assertIn('plan', refused.json())
        self.assertNotIn(ended.id, [p['id'] for p in self.as_user(self.alice).get('/api/catalog/plans/').json()])
        request = self.as_user(self.alice).post(f'/api/catalog/plans/{ended.id}/request/')
        self.assertEqual(request.status_code, 400)
        self.assertIn('no longer available', request.json()['detail'])

    def test_a_plan_that_has_not_started_is_not_offered(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        future = self.new_plan(product, name='Soon', start_date=TODAY + timedelta(days=5))
        self.assertNotIn(future.id, [p['id'] for p in self.as_user(self.alice).get('/api/catalog/plans/').json()])
        self.assertNotIn(future.id, [p['id'] for p in self.as_user(self.staff).get('/api/catalog/plans/').json()])
        too_early = self.as_user(self.staff).post('/api/subscriptions/', self.subscription_payload(product, future), format='json')
        self.assertEqual(too_early.status_code, 400)
        self.assertEqual(self.as_user(self.alice).post(f'/api/catalog/plans/{future.id}/request/').status_code, 404)

    def test_a_plan_open_today_is_offered_with_its_dates(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        open_plan = self.new_plan(product, name='Open', end_date=TODAY + timedelta(days=30))
        rows = {p['id']: p for p in self.as_user(self.alice).get('/api/catalog/plans/').json()}
        self.assertIn(open_plan.id, rows)
        self.assertEqual(rows[open_plan.id]['end_date'], str(TODAY + timedelta(days=30)))
        self.assertNotIn('cost_price', str(rows[open_plan.id]))

    def test_a_subscription_cannot_start_after_the_plan_ends(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        plan = self.new_plan(product, end_date=TODAY + timedelta(days=10))
        late = self.as_user(self.staff).post(
            '/api/subscriptions/', self.subscription_payload(product, plan, start_date=str(TODAY + timedelta(days=11))), format='json'
        )
        self.assertEqual(late.status_code, 400)
        self.assertIn('start_date', late.json())

    def test_a_switched_off_plan_cannot_be_subscribed_to(self):
        product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        plan = self.new_plan(product)
        self.assertEqual(self.as_user(self.admin).post(f'/api/plans/{plan.id}/deactivate/').json()['is_active'], False)
        self.assertNotIn(plan.id, [p['id'] for p in self.as_user(self.staff).get('/api/catalog/plans/').json()])
        response = self.as_user(self.staff).post('/api/subscriptions/', self.subscription_payload(product, plan), format='json')
        self.assertEqual(response.status_code, 400, 'staff can still sell a plan the admin switched off')
