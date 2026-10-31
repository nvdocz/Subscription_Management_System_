from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from billing.engine import run_billing
from billing.models import Invoice, Payment
from plans.models import SubscriptionPlan
from pricing.models import Discount, TaxRule
from products.models import Product
from subscriptions import services
from subscriptions.models import Subscription, SubscriptionLine

TODAY = timezone.localdate()


def make_plan(product, **overrides):
    values = dict(
        product=product,
        name='Monthly',
        price=Decimal('1000.00'),
        billing_frequency='monthly',
        start_date=TODAY - timedelta(days=60),
    )
    values.update(overrides)
    return SubscriptionPlan.objects.create(**values)


class BillingRulesTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('boss', 'boss@example.com', 'Boss#Pass123', role='admin')
        self.staff = User.objects.create_user('rep', 'rep@example.com', 'Rep#Pass1234', role='staff')
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'Alice#Pass12', role='customer')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'Bob#Pass1234', role='customer')
        self.product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        self.plan = make_plan(self.product)

    def subscribe(self, customer, quantity=1, start=None, **plan_overrides):
        plan = make_plan(self.product, **plan_overrides) if plan_overrides else self.plan
        subscription = Subscription.objects.create(
            customer=customer,
            plan=plan,
            quantity=quantity,
            start_date=start or TODAY,
            expiry_date=TODAY + timedelta(days=365),
            created_by=self.staff,
        )
        SubscriptionLine.objects.create(
            subscription=subscription, product=self.product, quantity=quantity, unit_price=plan.price
        )
        services.confirm(subscription, self.staff)
        subscription.refresh_from_db()
        return subscription

    def test_password_policy_matches_the_brief(self):
        weak = ['Short1!', 'alllowercase1!', 'ALLUPPERCASE1!', 'NoSpecial1234']
        for password in weak:
            response = self.client.post(
                '/api/auth/register/', {'username': 'x', 'email': 'x@example.com', 'password': password}, format='json'
            )
            self.assertEqual(response.status_code, 400, password)
        ok = self.client.post(
            '/api/auth/register/', {'username': 'newbie', 'email': 'newbie@example.com', 'password': 'Valid#Pass1'}, format='json'
        )
        self.assertEqual(ok.status_code, 201)

    def test_email_must_be_unique(self):
        response = self.client.post(
            '/api/auth/register/', {'username': 'other', 'email': 'ALICE@example.com', 'password': 'Valid#Pass1'}, format='json'
        )
        self.assertIn(response.status_code, (400,))

    def test_activation_creates_first_invoice_from_subscription_lines(self):
        subscription = self.subscribe(self.alice, quantity=2)
        self.assertEqual(subscription.status, 'active')
        invoice = subscription.invoices.get()
        self.assertEqual(invoice.status, 'confirmed')
        self.assertEqual(invoice.lines.count(), 1)
        self.assertEqual(invoice.subtotal, Decimal('2000.00'))
        self.assertEqual(invoice.due_date, TODAY + timedelta(days=15))

    def test_nothing_is_billed_twice(self):
        subscription = self.subscribe(self.alice)
        subscription.next_billing_date = TODAY + timedelta(days=3)
        subscription.save(update_fields=['next_billing_date'])
        later = TODAY + timedelta(days=3)
        first = run_billing(as_of=later, actor=self.staff)
        second = run_billing(as_of=later, actor=self.staff)
        self.assertEqual(first['invoices_created'], 1)
        self.assertEqual(second['invoices_created'], 0)
        self.assertEqual(subscription.invoices.count(), 2)
        periods = list(subscription.invoices.values_list('period_start', flat=True))
        self.assertEqual(len(periods), len(set(periods)))

    def test_missed_periods_are_caught_up_not_skipped(self):
        subscription = self.subscribe(self.alice, start=TODAY - timedelta(days=95), billing_frequency='monthly')
        self.assertGreaterEqual(subscription.invoices.count(), 3)

    def test_tax_comes_from_admin_rules_and_the_most_specific_rule_wins(self):
        TaxRule.objects.create(name='GST', rate=18)
        TaxRule.objects.create(name='Service tax', rate=12, product_type='service')
        subscription = self.subscribe(self.alice)
        invoice = subscription.invoices.get()
        self.assertEqual(invoice.lines.get().tax_rate, Decimal('12.00'))
        self.assertEqual(invoice.tax_total, Decimal('120.00'))
        self.assertEqual(invoice.amount, Decimal('1120.00'))

    def test_discount_applies_on_its_own_then_stops_when_used_up(self):
        Discount.objects.create(
            name='Seats 10%', kind='percentage', value=10, applies_to='subscription',
            min_quantity=3, start_date=TODAY - timedelta(days=1), usage_limit=1,
        )
        first = self.subscribe(self.alice, quantity=3).invoices.get()
        self.assertEqual(first.discount_total, Decimal('300.00'))
        self.assertEqual(first.discounts.get().name, 'Seats 10%')
        second = self.subscribe(self.bob, quantity=3).invoices.get()
        self.assertEqual(second.discount_total, Decimal('0.00'))

    def test_expired_discount_is_ignored(self):
        Discount.objects.create(
            name='Old offer', kind='fixed', value=100, applies_to='subscription',
            start_date=TODAY - timedelta(days=30), end_date=TODAY - timedelta(days=1),
        )
        invoice = self.subscribe(self.alice).invoices.get()
        self.assertEqual(invoice.discount_total, Decimal('0.00'))

    def test_payment_marks_invoice_paid_and_overpayment_is_rejected(self):
        invoice = self.subscribe(self.alice).invoices.get()
        self.client.force_authenticate(self.staff)
        too_much = self.client.post('/api/payments/', {'invoice': invoice.id, 'amount': '5000.00', 'method': 'cash'}, format='json')
        self.assertEqual(too_much.status_code, 400)
        ok = self.client.post(
            '/api/payments/', {'invoice': invoice.id, 'amount': str(invoice.amount), 'method': 'bank_transfer', 'note': 'Ref 42'}, format='json'
        )
        self.assertEqual(ok.status_code, 201)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'paid')
        self.assertEqual(Payment.objects.get().note, 'Ref 42')

    def test_customers_only_see_their_own_invoices_and_subscriptions(self):
        self.subscribe(self.alice)
        self.subscribe(self.bob)
        self.client.force_authenticate(self.alice)
        invoices = self.client.get('/api/invoices/').json()
        subscriptions = self.client.get('/api/subscriptions/').json()
        self.assertEqual(invoices['count'], 1)
        self.assertEqual(subscriptions['count'], 1)
        self.assertEqual(self.client.get('/api/payments/').json()['count'], 0)

    def test_only_admin_manages_discounts_and_staff_cannot_add_staff(self):
        payload = {'name': 'X', 'kind': 'fixed', 'value': '50', 'applies_to': 'subscription', 'start_date': str(TODAY)}
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post('/api/discounts/', payload, format='json').status_code, 403)
        self.assertEqual(self.client.get('/api/discounts/').status_code, 200)
        new_staff = {'username': 'new', 'email': 'new@example.com', 'password': 'Valid#Pass1', 'role': 'staff'}
        self.assertEqual(self.client.post('/api/auth/users/', new_staff, format='json').status_code, 400)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post('/api/discounts/', payload, format='json').status_code, 201)
        self.assertEqual(self.client.post('/api/auth/users/', new_staff, format='json').status_code, 201)

    def test_plan_lifecycle_options_limit_what_a_customer_can_do(self):
        subscription = self.subscribe(self.alice, allow_pause=False, allow_early_closure=False, allow_renewal=False)
        self.client.force_authenticate(self.alice)
        listing = self.client.get(f'/api/subscriptions/{subscription.id}/').json()
        self.assertEqual(listing['allowed_actions'], [])
        denied = self.client.post(f'/api/subscriptions/{subscription.id}/do/pause/')
        self.assertEqual(denied.status_code, 403)

    def test_customer_can_pause_and_resume_when_the_plan_allows_it(self):
        subscription = self.subscribe(self.alice)
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.post(f'/api/subscriptions/{subscription.id}/do/pause/').json()['status'], 'paused')
        self.assertEqual(self.client.post(f'/api/subscriptions/{subscription.id}/do/resume/').json()['status'], 'active')

    def test_plans_with_automatic_closure_close_after_expiry(self):
        subscription = self.subscribe(self.alice, auto_close_enabled=True)
        Subscription.objects.filter(pk=subscription.pk).update(expiry_date=TODAY - timedelta(days=1))
        run_billing(as_of=TODAY, actor=self.staff)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, 'closed')

    def test_invoice_moves_draft_to_confirmed_to_paid(self):
        subscription = self.subscribe(self.alice)
        next_cycle = subscription.next_billing_date
        run_billing(as_of=next_cycle, actor=self.staff, confirm=False)
        draft = subscription.invoices.get(status='draft')
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(f'/api/invoices/{draft.id}/confirm/').json()['status'], 'confirmed')
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.post(f'/api/invoices/{draft.id}/pay/').json()['status'], 'paid')

    def test_expired_subscriptions_are_not_listed_as_due_and_nothing_is_billed(self):
        subscription = self.subscribe(self.alice)
        Subscription.objects.filter(pk=subscription.pk).update(
            expiry_date=TODAY - timedelta(days=2), next_billing_date=TODAY - timedelta(days=1)
        )
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get('/api/billing/preview/').json()['due_count'], 0)
        result = run_billing(as_of=TODAY, actor=self.staff)
        self.assertEqual(result['invoices_created'], 0)

    def test_payment_dates_must_be_real(self):
        invoice = self.subscribe(self.alice).invoices.get()
        self.client.force_authenticate(self.staff)
        future = self.client.post(
            '/api/payments/', {'invoice': invoice.id, 'amount': '10.00', 'method': 'cash', 'paid_on': str(TODAY + timedelta(days=2))}, format='json'
        )
        before = self.client.post(
            '/api/payments/', {'invoice': invoice.id, 'amount': '10.00', 'method': 'cash', 'paid_on': str(invoice.issue_date - timedelta(days=1))}, format='json'
        )
        self.assertEqual(future.status_code, 400)
        self.assertEqual(before.status_code, 400)
        today = self.client.post(
            '/api/payments/', {'invoice': invoice.id, 'amount': '10.00', 'method': 'cash', 'paid_on': str(TODAY)}, format='json'
        )
        self.assertEqual(today.status_code, 201)

    def test_late_invoices_are_issued_today_and_are_not_born_overdue(self):
        subscription = self.subscribe(self.alice)
        Subscription.objects.filter(pk=subscription.pk).update(next_billing_date=TODAY - timedelta(days=40))
        run_billing(as_of=TODAY, actor=self.staff, confirm=True)
        late = subscription.invoices.exclude(period_start=subscription.invoices.order_by('period_start').first().period_start)
        self.assertTrue(late.exists())
        for invoice in late:
            self.assertEqual(invoice.issue_date, TODAY)
            self.assertEqual(invoice.due_date, TODAY + timedelta(days=15))
            self.assertFalse(invoice.is_overdue)

    def test_a_discount_created_today_applies_to_invoices_created_today_for_older_periods(self):
        subscription = self.subscribe(self.alice)
        Subscription.objects.filter(pk=subscription.pk).update(next_billing_date=TODAY - timedelta(days=1))
        Discount.objects.create(name='Today only', kind='fixed', value=50, start_date=TODAY)
        run_billing(as_of=TODAY, actor=self.staff, confirm=True)
        newest = subscription.invoices.order_by('-id').first()
        self.assertEqual(newest.discount_total, Decimal('50.00'))

    def test_percentage_discounts_come_off_first_then_fixed_whatever_the_creation_order(self):
        for first_kind in ('fixed', 'percentage'):
            with self.subTest(created_first=first_kind):
                Discount.objects.all().delete()
                Invoice.objects.all().delete()
                Subscription.objects.all().delete()
                specs = {'fixed': dict(name='Flat', kind='fixed', value=100), 'percentage': dict(name='Ten', kind='percentage', value=10)}
                order = [first_kind, 'percentage' if first_kind == 'fixed' else 'fixed']
                for kind in order:
                    Discount.objects.create(start_date=TODAY - timedelta(days=1), **specs[kind])
                invoice = self.subscribe(self.alice).invoices.get()
                self.assertEqual(invoice.discount_total, Decimal('200.00'))
                self.assertEqual([d.name for d in invoice.discounts.order_by('id')], ['Ten', 'Flat'])

    def test_a_month_end_subscription_keeps_billing_on_the_last_day(self):
        subscription = Subscription.objects.create(
            customer=self.alice, plan=self.plan, status='active', start_date=date(2026, 1, 31),
            expiry_date=date(2027, 1, 31), next_billing_date=date(2026, 1, 31), created_by=self.staff,
        )
        SubscriptionLine.objects.create(subscription=subscription, product=self.product, quantity=1, unit_price=1000)
        run_billing(as_of=date(2026, 5, 1), actor=self.staff)
        starts = list(subscription.invoices.order_by('period_start').values_list('period_start', flat=True))
        self.assertEqual(starts, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)])
        ends = list(subscription.invoices.order_by('period_start').values_list('period_end', flat=True))
        self.assertEqual(ends, [date(2026, 2, 27), date(2026, 3, 30), date(2026, 4, 29), date(2026, 5, 30)])
