"""PDF stories: the subscription lifecycle, billing day, discounts, taxes, payments and the finance lead's reports."""

from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.db.models import Count
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from billing.engine import build_invoice, preview_billing, run_billing
from billing.models import Invoice, InvoiceLine, Payment
from plans.models import SubscriptionPlan
from pricing.models import Discount, TaxRule, tax_rate_for
from products.models import Product
from quotations.models import Quotation
from subscriptions import services
from subscriptions.models import Subscription, SubscriptionLine, activate_due_subscriptions

FAST = dict(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
TODAY = timezone.localdate()


def days_ago(n):
    return TODAY - timedelta(days=n)


@override_settings(**FAST)
class FlowCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('boss', 'boss@example.com', 'Boss#Pass123', role='admin')
        self.staff = User.objects.create_user('rep', 'rep@example.com', 'Rep#Pass1234', role='staff')
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'Alice#Pass12', role='customer')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'Bob#Pass1234', role='customer')
        self.product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        self.plan = self.make_plan()
        self.staff_api = self.api(self.staff)
        self.admin_api = self.api(self.admin)
        self.alice_api = self.api(self.alice)
        self.bob_api = self.api(self.bob)

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def make_plan(self, product=None, **overrides):
        values = dict(
            product=product or self.product, name='Monthly', price=Decimal('1000.00'), billing_frequency='monthly',
            start_date=days_ago(60),
        )
        values.update(overrides)
        return SubscriptionPlan.objects.create(**values)

    def make_subscription(self, customer, status='active', plan=None, lines=None, start=None, next_billing=None, expiry=None, **extra):
        plan = plan or self.plan
        subscription = Subscription.objects.create(
            customer=customer, plan=plan, status=status, start_date=start or TODAY,
            expiry_date=expiry or TODAY + timedelta(days=365), next_billing_date=next_billing,
            created_by=self.staff, **extra,
        )
        for product, quantity, price in lines or [(self.product, 1, plan.price)]:
            SubscriptionLine.objects.create(subscription=subscription, product=product, quantity=quantity, unit_price=price)
        return subscription

    def activate(self, customer, lines=None, plan=None, **extra):
        """A subscription taken through confirm, so it is active with its first invoice already issued."""
        subscription = self.make_subscription(customer, 'draft', plan, lines, **extra)
        services.confirm(subscription, self.staff)
        subscription.refresh_from_db()
        return subscription

    def payload(self, **overrides):
        payload = {
            'customer': self.alice.id,
            'plan': self.plan.id,
            'start_date': str(TODAY),
            'payment_terms': 'net_15',
            'lines': [{'product': self.product.id, 'quantity': 1, 'unit_price': '1000.00'}],
        }
        payload.update(overrides)
        return payload

    def do(self, client, subscription, action):
        return client.post(f'/api/subscriptions/{subscription.id}/do/{action}/')


# ====================================================================================== lifecycle


class LifecycleTests(FlowCase):
    def test_staff_walk_a_subscription_from_draft_to_active(self):
        created = self.staff_api.post('/api/subscriptions/', self.payload(payment_terms='net_30'), format='json')
        self.assertEqual(created.status_code, 201, created.content)
        body = created.json()
        self.assertEqual(body['status'], 'draft')
        self.assertRegex(body['number'], r'^SUB-\d{5}$')
        self.assertEqual(body['expiry_date'], str(TODAY + timedelta(days=365)))
        self.assertEqual(body['payment_terms'], 'net_30')
        self.assertEqual(set(body['allowed_actions']), {'send_quotation', 'confirm', 'close'})
        subscription_id = body['id']

        sent = self.staff_api.post(f'/api/subscriptions/{subscription_id}/do/send_quotation/').json()
        self.assertEqual(sent['status'], 'quotation')
        self.assertEqual(set(sent['allowed_actions']), {'confirm', 'close'})

        active = self.staff_api.post(f'/api/subscriptions/{subscription_id}/do/confirm/').json()
        self.assertEqual(active['status'], 'active')
        self.assertEqual(set(active['allowed_actions']), {'pause', 'close', 'renew'})
        self.assertEqual(active['next_billing_date'], str(self.plan.next_billing_after(TODAY)))
        messages = [e['message'] for e in active['events']]
        for expected in ('Subscription created', 'Quotation sent to the customer', 'Subscription confirmed', 'Subscription activated'):
            self.assertIn(expected, messages)
        self.assertTrue(any(m.startswith('First invoice INV-') for m in messages))

        invoices = self.staff_api.get(f'/api/invoices/?subscription={subscription_id}').json()['results']
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices[0]['status'], 'confirmed')
        self.assertEqual(invoices[0]['due_date'], str(TODAY + timedelta(days=30)))

    def test_a_subscription_can_skip_the_quotation_stage(self):
        subscription = self.make_subscription(self.alice, 'draft')
        self.assertEqual(self.do(self.staff_api, subscription, 'confirm').json()['status'], 'active')

    def test_a_future_start_stays_confirmed_until_its_start_date_then_bills(self):
        start = TODAY + timedelta(days=10)
        created = self.staff_api.post('/api/subscriptions/', self.payload(start_date=str(start)), format='json').json()
        subscription_id = created['id']
        confirmed = self.staff_api.post(f'/api/subscriptions/{subscription_id}/do/confirm/').json()
        self.assertEqual(confirmed['status'], 'confirmed')
        self.assertEqual(set(confirmed['allowed_actions']), {'activate', 'close'})
        too_early = self.staff_api.post(f'/api/subscriptions/{subscription_id}/do/activate/')
        self.assertEqual(too_early.status_code, 400)
        self.assertIn('starts on', ' '.join(too_early.json()))
        self.assertEqual(Invoice.objects.count(), 0)

        self.assertEqual(activate_due_subscriptions(TODAY + timedelta(days=9)), 0)
        self.assertEqual(Subscription.objects.get(pk=subscription_id).status, 'confirmed')
        self.assertEqual(activate_due_subscriptions(start), 1)
        subscription = Subscription.objects.get(pk=subscription_id)
        self.assertEqual((subscription.status, subscription.next_billing_date), ('active', start))

        result = run_billing(as_of=start, actor=self.staff)
        self.assertEqual(result['invoices_created'], 1)
        invoice = subscription.invoices.get()
        self.assertEqual((invoice.period_start, invoice.issue_date), (start, start))

    def test_allowed_actions_at_every_status_for_staff_and_customers(self):
        staff_expected = {
            'draft': {'send_quotation', 'confirm', 'close'},
            'quotation': {'confirm', 'close'},
            'confirmed': {'activate', 'close'},
            'active': {'pause', 'close', 'renew'},
            'paused': {'resume', 'close'},
            'closed': {'renew'},
        }
        customer_expected = {
            'draft': None,
            'quotation': set(),
            'confirmed': set(),
            'active': {'pause', 'close', 'renew'},
            'paused': {'resume', 'close'},
            'closed': {'renew'},
        }
        for status, expected in staff_expected.items():
            extra = {'end_date': TODAY} if status == 'closed' else {}
            subscription = self.make_subscription(self.alice, status, next_billing=TODAY + timedelta(days=5), **extra)
            with self.subTest(status=status, who='staff'):
                body = self.staff_api.get(f'/api/subscriptions/{subscription.id}/').json()
                self.assertEqual(set(body['allowed_actions']), expected)
            with self.subTest(status=status, who='customer'):
                response = self.alice_api.get(f'/api/subscriptions/{subscription.id}/')
                if customer_expected[status] is None:
                    self.assertEqual(response.status_code, 404)
                else:
                    self.assertEqual(set(response.json()['allowed_actions']), customer_expected[status])

    def test_invalid_transitions_are_refused_with_403_and_change_nothing(self):
        cases = [
            ('draft', 'activate'), ('draft', 'pause'), ('draft', 'resume'), ('draft', 'renew'),
            ('quotation', 'activate'), ('quotation', 'pause'), ('confirmed', 'pause'), ('confirmed', 'resume'),
            ('active', 'resume'), ('active', 'confirm'), ('active', 'send_quotation'), ('active', 'activate'),
            ('paused', 'pause'), ('paused', 'confirm'), ('closed', 'close'), ('closed', 'pause'), ('closed', 'confirm'),
            ('closed', 'resume'), ('draft', 'explode'),
        ]
        for status, action in cases:
            with self.subTest(status=status, action=action):
                subscription = self.make_subscription(self.alice, status, next_billing=TODAY + timedelta(days=5))
                response = self.do(self.staff_api, subscription, action)
                self.assertEqual(response.status_code, 403, response.content)
                subscription.refresh_from_db()
                self.assertEqual(subscription.status, status)

    def test_a_customer_cannot_run_staff_only_actions(self):
        subscription = self.make_subscription(self.alice, 'active', next_billing=TODAY + timedelta(days=5))
        for action in ('confirm', 'activate', 'send_quotation', 'resume'):
            self.assertEqual(self.do(self.alice_api, subscription, action).status_code, 403, action)

    def test_confirm_needs_at_least_one_line(self):
        subscription = Subscription.objects.create(customer=self.alice, plan=self.plan, start_date=TODAY, created_by=self.staff)
        self.assertEqual(self.do(self.staff_api, subscription, 'confirm').status_code, 400)
        self.assertEqual(self.do(self.staff_api, subscription, 'send_quotation').status_code, 400)

    def test_pausing_stops_billing_and_resuming_does_not_back_bill_the_gap(self):
        subscription = self.make_subscription(self.alice, 'active', start=days_ago(60), next_billing=days_ago(5))
        paused = self.do(self.staff_api, subscription, 'pause')
        self.assertEqual(paused.json()['status'], 'paused')
        self.assertEqual(run_billing(as_of=TODAY, actor=self.staff)['invoices_created'], 0)
        self.assertEqual(run_billing(as_of=TODAY + timedelta(days=60), actor=self.staff)['invoices_created'], 0)
        self.assertEqual(preview_billing(TODAY)['due_count'], 0)
        self.assertEqual(Invoice.objects.count(), 0)

        resumed = self.do(self.staff_api, subscription, 'resume')
        self.assertEqual(resumed.json()['status'], 'active')
        subscription.refresh_from_db()
        self.assertEqual(subscription.next_billing_date, TODAY)
        self.assertEqual(run_billing(as_of=TODAY, actor=self.staff)['invoices_created'], 1)
        invoice = subscription.invoices.get()
        self.assertEqual(invoice.period_start, TODAY, 'paused periods must not be billed afterwards')

    def test_closing_sets_the_end_date_and_stops_billing(self):
        subscription = self.make_subscription(self.alice, 'active', next_billing=TODAY)
        closed = self.do(self.staff_api, subscription, 'close').json()
        self.assertEqual(closed['status'], 'closed')
        self.assertEqual(closed['end_date'], str(TODAY))
        self.assertEqual(run_billing(as_of=TODAY, actor=self.staff)['invoices_created'], 0)
        self.assertEqual(self.do(self.staff_api, subscription, 'close').status_code, 403)

    def test_renewing_an_active_subscription_extends_the_term_by_a_year(self):
        expiry = TODAY + timedelta(days=10)
        subscription = self.make_subscription(self.alice, 'active', expiry=expiry, next_billing=TODAY + timedelta(days=5))
        renewed = self.do(self.alice_api, subscription, 'renew').json()
        self.assertEqual(renewed['status'], 'active')
        self.assertEqual(renewed['expiry_date'], str(expiry + timedelta(days=365)))

    def test_renewing_a_closed_subscription_reactivates_and_bills_it(self):
        subscription = self.make_subscription(
            self.alice, 'closed', start=days_ago(200), expiry=days_ago(20), next_billing=days_ago(30), end_date=days_ago(10)
        )
        renewed = self.do(self.staff_api, subscription, 'renew').json()
        self.assertEqual(renewed['status'], 'active')
        self.assertEqual(renewed['expiry_date'], str(TODAY + timedelta(days=365)))
        self.assertIsNone(renewed['end_date'])
        subscription.refresh_from_db()
        invoice = subscription.invoices.get()
        self.assertEqual((invoice.status, invoice.period_start), ('confirmed', TODAY))
        self.assertEqual(subscription.next_billing_date, self.plan.next_billing_after(TODAY))

    def test_plans_that_close_themselves_close_after_expiry_and_others_stay_open(self):
        auto = self.make_plan(name='Auto', auto_close_enabled=True)
        manual = self.make_plan(name='Manual', auto_close_enabled=False)
        closing = self.make_subscription(self.alice, 'active', plan=auto, expiry=days_ago(1), next_billing=TODAY + timedelta(days=30))
        staying = self.make_subscription(self.bob, 'active', plan=manual, expiry=days_ago(1), next_billing=TODAY)
        result = run_billing(as_of=TODAY, actor=self.staff)
        self.assertEqual(result['auto_closed'], 1)
        self.assertEqual(result['invoices_created'], 0, 'nothing may be billed past the expiry date')
        closing.refresh_from_db()
        staying.refresh_from_db()
        self.assertEqual((closing.status, closing.end_date), ('closed', TODAY))
        self.assertEqual(staying.status, 'active')
        self.assertEqual(preview_billing(TODAY)['due_count'], 0)

    def test_listing_subscriptions_also_closes_the_expired_ones(self):
        auto = self.make_plan(name='Auto', auto_close_enabled=True)
        subscription = self.make_subscription(self.alice, 'active', plan=auto, expiry=days_ago(3), next_billing=TODAY + timedelta(days=30))
        self.staff_api.get('/api/subscriptions/')
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, 'closed')


class CustomerPlanOptionTests(FlowCase):
    def customer_actions(self, subscription):
        return set(self.alice_api.get(f'/api/subscriptions/{subscription.id}/').json()['allowed_actions'])

    def test_each_plan_option_switches_one_customer_action_on_or_off(self):
        cases = [
            ({'allow_pause': False}, {'close', 'renew'}),
            ({'allow_early_closure': False}, {'pause', 'renew'}),
            ({'allow_renewal': False}, {'pause', 'close'}),
            ({'allow_pause': False, 'allow_early_closure': False, 'allow_renewal': False}, set()),
        ]
        for flags, expected in cases:
            with self.subTest(flags=flags):
                plan = self.make_plan(name=str(flags), **flags)
                subscription = self.make_subscription(self.alice, 'active', plan=plan, next_billing=TODAY + timedelta(days=5))
                self.assertEqual(self.customer_actions(subscription), expected)

    def test_a_refused_action_is_refused_by_the_server_not_just_hidden(self):
        plan = self.make_plan(allow_pause=False, allow_early_closure=False, allow_renewal=False)
        subscription = self.make_subscription(self.alice, 'active', plan=plan, next_billing=TODAY + timedelta(days=5))
        for action in ('pause', 'close', 'renew'):
            self.assertEqual(self.do(self.alice_api, subscription, action).status_code, 403, action)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, 'active')

    def test_a_customer_can_pause_resume_and_close_when_the_plan_allows(self):
        subscription = self.make_subscription(self.alice, 'active', next_billing=TODAY + timedelta(days=5))
        self.assertEqual(self.do(self.alice_api, subscription, 'pause').json()['status'], 'paused')
        self.assertEqual(self.do(self.alice_api, subscription, 'resume').json()['status'], 'active')
        closed = self.do(self.alice_api, subscription, 'close').json()
        self.assertEqual((closed['status'], closed['end_date']), ('closed', str(TODAY)))

    def test_a_customer_can_renew_a_closed_subscription_only_while_the_plan_is_on_sale(self):
        subscription = self.make_subscription(
            self.alice, 'closed', start=days_ago(100), expiry=days_ago(5), next_billing=days_ago(10), end_date=days_ago(5)
        )
        self.assertEqual(self.customer_actions(subscription), {'renew'})
        self.plan.is_active = False
        self.plan.save()
        self.assertEqual(self.customer_actions(subscription), set())

    def test_a_customer_cannot_touch_someone_elses_subscription(self):
        subscription = self.make_subscription(self.bob, 'active', next_billing=TODAY + timedelta(days=5))
        self.assertEqual(self.do(self.alice_api, subscription, 'close').status_code, 404)
        self.assertEqual(self.alice_api.get(f'/api/subscriptions/{subscription.id}/').status_code, 404)


class SubscriptionRulesTests(FlowCase):
    def test_only_draft_and_quotation_subscriptions_can_be_edited(self):
        created = self.staff_api.post('/api/subscriptions/', self.payload(), format='json').json()
        url = f'/api/subscriptions/{created["id"]}/'
        edited = self.staff_api.patch(url, {
            'payment_terms': 'net_45', 'lines': [{'product': self.product.id, 'quantity': 4, 'unit_price': '250.00'}],
        }, format='json')
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertEqual(edited.json()['payment_terms'], 'net_45')
        self.assertEqual([(l['quantity'], l['unit_price']) for l in edited.json()['lines']], [(4, '250.00')])

        self.staff_api.post(f'{url}do/send_quotation/')
        self.assertEqual(self.staff_api.patch(url, {'payment_terms': 'net_30'}, format='json').status_code, 200)

        self.staff_api.post(f'{url}do/confirm/')
        locked = self.staff_api.patch(url, {'payment_terms': 'immediate'}, format='json')
        self.assertEqual(locked.status_code, 400)
        self.assertEqual(Subscription.objects.get(pk=created['id']).payment_terms, 'net_30')

    def test_only_drafts_can_be_deleted(self):
        draft = self.make_subscription(self.alice, 'draft')
        stage = self.make_subscription(self.alice, 'quotation')
        live = self.make_subscription(self.alice, 'active', next_billing=TODAY + timedelta(days=5))
        self.assertEqual(self.staff_api.delete(f'/api/subscriptions/{stage.id}/').status_code, 400)
        self.assertEqual(self.staff_api.delete(f'/api/subscriptions/{live.id}/').status_code, 400)
        self.assertEqual(self.staff_api.delete(f'/api/subscriptions/{draft.id}/').status_code, 204)
        self.assertEqual(Subscription.objects.count(), 2)

    def test_customers_cannot_create_edit_or_delete_subscriptions(self):
        subscription = self.make_subscription(self.alice, 'draft')
        self.assertEqual(self.alice_api.post('/api/subscriptions/', self.payload(), format='json').status_code, 403)
        subscription = self.make_subscription(self.alice, 'quotation')
        self.assertEqual(self.alice_api.patch(f'/api/subscriptions/{subscription.id}/', {'payment_terms': 'immediate'}, format='json').status_code, 403)
        self.assertEqual(self.alice_api.delete(f'/api/subscriptions/{subscription.id}/').status_code, 403)

    def test_creation_validates_the_basics(self):
        cases = {
            'expiry before start': ({'expiry_date': str(TODAY - timedelta(days=1))}, 'expiry_date'),
            'customer is staff': ({'customer': self.staff.id}, 'customer'),
            'no lines': ({'lines': []}, 'lines'),
            'no plan': ({'plan': None}, 'plan'),
            'unknown product': ({'lines': [{'product': 99999, 'quantity': 1, 'unit_price': '10.00'}]}, 'lines'),
            'bad payment terms': ({'payment_terms': 'whenever'}, 'payment_terms'),
        }
        for label, (override, key) in cases.items():
            with self.subTest(label):
                response = self.staff_api.post('/api/subscriptions/', self.payload(**override), format='json')
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn(key, response.json())
        self.assertEqual(Subscription.objects.count(), 0)

    def test_line_numbers_must_make_sense(self):
        cases = {
            'negative price': {'product': self.product.id, 'quantity': 1, 'unit_price': '-10.00'},
            'zero quantity': {'product': self.product.id, 'quantity': 0, 'unit_price': '10.00'},
            'tax above 100%': {'product': self.product.id, 'quantity': 1, 'unit_price': '10.00', 'tax_rate': '150.00'},
        }
        for label, line in cases.items():
            with self.subTest(label):
                response = self.staff_api.post('/api/subscriptions/', self.payload(lines=[line]), format='json')
                self.assertEqual(response.status_code, 400, f'{label} was accepted')

    def test_the_plans_minimum_quantity_is_enforced(self):
        plan = self.make_plan(name='Teams', min_quantity=5)
        too_few = self.payload(plan=plan.id, lines=[{'product': self.product.id, 'quantity': 2, 'unit_price': '10.00'}])
        self.assertEqual(self.staff_api.post('/api/subscriptions/', too_few, format='json').status_code, 400, 'below the minimum quantity')
        enough = self.payload(plan=plan.id, lines=[{'product': self.product.id, 'quantity': 5, 'unit_price': '10.00'}])
        self.assertEqual(self.staff_api.post('/api/subscriptions/', enough, format='json').status_code, 201)

    def test_list_filters_and_pagination(self):
        for index in range(25):
            self.make_subscription(self.alice, 'active', next_billing=TODAY + timedelta(days=5))
        self.make_subscription(self.bob, 'paused')
        page = self.staff_api.get('/api/subscriptions/?page_size=10').json()
        self.assertEqual((page['count'], len(page['results'])), (26, 10))
        self.assertEqual(self.staff_api.get('/api/subscriptions/?status=paused').json()['count'], 1)
        self.assertEqual(self.staff_api.get('/api/subscriptions/?q=bob').json()['count'], 1)
        self.assertEqual(self.staff_api.get(f'/api/subscriptions/?customer={self.alice.id}').json()['count'], 25)
        self.assertEqual(self.staff_api.get('/api/subscriptions/?status=active,paused').json()['count'], 26)


# ====================================================================================== billing day


class BillingDayTests(FlowCase):
    def test_a_billing_run_bills_only_active_subscriptions_that_are_due(self):
        due = self.make_subscription(self.alice, 'active', next_billing=TODAY)
        self.make_subscription(self.bob, 'active', next_billing=TODAY + timedelta(days=5))
        self.make_subscription(self.bob, 'paused', next_billing=TODAY)
        self.make_subscription(self.bob, 'closed', next_billing=TODAY, end_date=TODAY)
        self.make_subscription(self.bob, 'draft', next_billing=TODAY)
        self.make_subscription(self.bob, 'quotation', next_billing=TODAY)
        self.assertEqual(preview_billing(TODAY)['due_count'], 1)
        result = run_billing(as_of=TODAY, actor=self.staff)
        self.assertEqual(result['invoices_created'], 1)
        self.assertEqual(Invoice.objects.get().subscription_id, due.id)

    def test_the_api_runs_and_previews_the_same_thing(self):
        self.make_subscription(self.alice, 'active', next_billing=TODAY)
        preview = self.staff_api.get('/api/billing/preview/').json()
        self.assertEqual(preview['due_count'], 1)
        self.assertEqual(float(preview['estimated_total']), 1000.0)
        self.assertEqual(preview['rows'][0]['customer'], 'alice')
        run = self.staff_api.post('/api/billing/run/', {'confirm': True}, format='json').json()
        self.assertEqual((run['invoices_created'], float(run['total_billed'])), (1, 1000.0))
        self.assertEqual(Invoice.objects.get().status, 'confirmed')
        self.assertEqual(self.staff_api.post('/api/billing/run/', {}, format='json').json()['invoices_created'], 0)

    def test_a_run_without_confirm_leaves_drafts_for_review(self):
        self.make_subscription(self.alice, 'active', next_billing=TODAY)
        self.staff_api.post('/api/billing/run/', {}, format='json')
        self.assertEqual(Invoice.objects.get().status, 'draft')
        self.assertEqual(self.staff_api.post('/api/invoices/confirm-drafts/').json()['confirmed'], 1)
        self.assertEqual(Invoice.objects.get().status, 'confirmed')

    def test_hundreds_of_subscriptions_are_billed_exactly_once(self):
        total = 150
        User.objects.bulk_create([
            User(username=f'bulk{i}', email=f'bulk{i}@example.com', role='customer', password='!') for i in range(total)
        ])
        customers = list(User.objects.filter(username__startswith='bulk').order_by('id'))
        Subscription.objects.bulk_create([
            Subscription(
                customer=customer, plan=self.plan, status='active', start_date=days_ago(30),
                expiry_date=TODAY + timedelta(days=300), next_billing_date=TODAY,
            )
            for customer in customers
        ])
        subscriptions = list(Subscription.objects.filter(customer__in=customers))
        SubscriptionLine.objects.bulk_create([
            SubscriptionLine(subscription=s, product=self.product, quantity=1, unit_price=1000) for s in subscriptions
        ])
        self.assertEqual(preview_billing(TODAY)['due_count'], total)

        first = run_billing(as_of=TODAY, actor=self.staff, confirm=True)
        self.assertEqual(first['invoices_created'], total)
        self.assertEqual(first['periods_skipped'], 0)
        self.assertEqual(first['total_billed'], Decimal('1000.00') * total)

        per_subscription = Invoice.objects.filter(subscription__in=subscriptions).values('subscription').annotate(n=Count('id'))
        self.assertEqual(len(per_subscription), total, 'a subscription was skipped')
        self.assertEqual({row['n'] for row in per_subscription}, {1}, 'a subscription was billed twice')
        self.assertEqual(Subscription.objects.filter(pk__in=[s.pk for s in subscriptions], next_billing_date=TODAY).count(), 0)

        second = run_billing(as_of=TODAY, actor=self.staff, confirm=True)
        self.assertEqual((second['invoices_created'], second['periods_skipped']), (0, 0))
        self.assertEqual(Invoice.objects.count(), total)

    def test_catching_up_after_a_long_gap_bills_every_missed_period_once(self):
        subscription = self.make_subscription(self.alice, 'active', start=days_ago(95), next_billing=days_ago(95), expiry=TODAY + timedelta(days=200))
        run_billing(as_of=TODAY, actor=self.staff, confirm=True)
        starts = list(subscription.invoices.order_by('period_start').values_list('period_start', flat=True))
        self.assertGreaterEqual(len(starts), 3)
        self.assertEqual(len(starts), len(set(starts)))
        boundary = days_ago(95)
        for start in starts:
            self.assertEqual(start, boundary)
            boundary = self.plan.next_billing_after(boundary)
        subscription.refresh_from_db()
        self.assertGreater(subscription.next_billing_date, TODAY)

    def test_the_database_itself_refuses_a_second_invoice_for_the_same_period(self):
        from django.db import IntegrityError, transaction

        subscription = self.make_subscription(self.alice, 'active', next_billing=TODAY)
        first = build_invoice(subscription, TODAY)
        with self.assertRaises(IntegrityError), transaction.atomic():
            build_invoice(subscription, TODAY)
        first.status = 'cancelled'
        first.save()
        self.assertEqual(build_invoice(subscription, TODAY).period_start, TODAY, 'a cancelled period may be issued again')

    def test_each_billing_frequency_bills_with_the_right_period_end(self):
        expected_days = {'daily': 1, 'weekly': 7}
        for frequency, length in expected_days.items():
            plan = self.make_plan(name=frequency, billing_frequency=frequency)
            subscription = self.make_subscription(self.alice, 'active', plan=plan, next_billing=TODAY)
            invoice = build_invoice(subscription, TODAY)
            self.assertEqual((invoice.period_end - invoice.period_start).days, length - 1, frequency)
        monthly = build_invoice(self.make_subscription(self.bob, 'active', next_billing=date_of(2026, 1, 31)), date_of(2026, 1, 31))
        self.assertEqual(monthly.period_end, date_of(2026, 2, 27))

    def test_invoice_carries_customer_lines_taxes_and_correct_totals(self):
        TaxRule.objects.create(name='GST', rate=18)
        subscription = self.activate(self.alice, lines=[(self.product, 3, Decimal('333.33'))])
        invoice = subscription.invoices.get()
        self.assertEqual(invoice.customer_id, self.alice.id)
        self.assertEqual((invoice.subtotal, invoice.discount_total, invoice.tax_total, invoice.amount), (
            Decimal('999.99'), Decimal('0.00'), Decimal('180.00'), Decimal('1179.99'),
        ))
        detail = self.staff_api.get(f'/api/invoices/{invoice.id}/').json()
        self.assertEqual(detail['customer_detail']['username'], 'alice')
        self.assertEqual(detail['subscription_number'], subscription.number)
        line = detail['lines'][0]
        self.assertEqual((line['quantity'], line['unit_price'], line['tax_rate']), (3, '333.33', '18.00'))
        self.assertEqual((line['subtotal'], line['tax'], line['total']), ('999.99', '180.00', '1179.99'))
        self.assertIn('CRM', line['description'])
        self.assertEqual(detail['period_start'], str(TODAY))

    def test_invoice_totals_equal_the_sum_of_their_lines(self):
        TaxRule.objects.create(name='GST', rate=18)
        other = Product.objects.create(name='Support', product_type='goods', sales_price=50, cost_price=10)
        TaxRule.objects.create(name='Goods', rate=5, product_type='goods')
        subscription = self.activate(
            self.alice, lines=[(self.product, 3, Decimal('333.33')), (other, 7, Decimal('19.99')), (self.product, 1, Decimal('0.01'))]
        )
        invoice = subscription.invoices.get()
        lines = list(invoice.lines.all())
        self.assertEqual(invoice.subtotal, sum(l.subtotal for l in lines))
        self.assertEqual(invoice.tax_total, sum(l.tax for l in lines))
        self.assertEqual(invoice.amount, invoice.subtotal - invoice.discount_total + invoice.tax_total)
        self.assertEqual(sorted(l.tax_rate for l in lines), [Decimal('5.00'), Decimal('18.00'), Decimal('18.00')])

    def test_tax_rounds_half_up_the_way_an_invoice_should(self):
        TaxRule.objects.create(name='Five', rate=5)
        subscription = self.activate(self.alice, lines=[(self.product, 1, Decimal('2.50'))])
        self.assertEqual(subscription.invoices.get().tax_total, Decimal('0.13'), '2.50 at 5% is 0.125 and must round up to 0.13')


def date_of(year, month, day):
    from datetime import date

    return date(year, month, day)


class TaxRuleTests(FlowCase):
    def setUp(self):
        super().setUp()
        self.goods = Product.objects.create(name='Box', product_type='goods', sales_price=10, cost_price=5)

    def test_the_most_specific_active_rule_wins(self):
        self.assertEqual(tax_rate_for(self.product), Decimal('0.00'))
        everything = TaxRule.objects.create(name='All', rate=18)
        self.assertEqual((tax_rate_for(self.product), tax_rate_for(self.goods)), (Decimal('18.00'), Decimal('18.00')))
        services_rule = TaxRule.objects.create(name='Services', rate=12, product_type='service')
        self.assertEqual((tax_rate_for(self.product), tax_rate_for(self.goods)), (Decimal('12.00'), Decimal('18.00')))
        special = TaxRule.objects.create(name='One product', rate=5, product=self.product)
        self.assertEqual((tax_rate_for(self.product), tax_rate_for(self.goods)), (Decimal('5.00'), Decimal('18.00')))
        special.is_active = False
        special.save()
        self.assertEqual(tax_rate_for(self.product), Decimal('12.00'))
        services_rule.is_active = False
        services_rule.save()
        self.assertEqual(tax_rate_for(self.product), Decimal('18.00'))
        everything.is_active = False
        everything.save()
        self.assertEqual((tax_rate_for(self.product), tax_rate_for(self.goods)), (Decimal('0.00'), Decimal('0.00')))

    def test_a_more_specific_rule_wins_even_when_its_rate_is_lower(self):
        TaxRule.objects.create(name='All', rate=28)
        TaxRule.objects.create(name='Product', rate=0, product=self.product)
        self.assertEqual(tax_rate_for(self.product), Decimal('0.00'))
        self.assertEqual(tax_rate_for(self.goods), Decimal('28.00'))

    def test_new_invoices_follow_the_rules_when_the_admin_changes_them(self):
        rule = TaxRule.objects.create(name='GST', rate=18)
        subscription = self.activate(self.alice)
        self.assertEqual(subscription.invoices.get().tax_total, Decimal('180.00'))
        rule.rate = 5
        rule.save()
        next_period = subscription.next_billing_date
        run_billing(as_of=next_period, actor=self.staff, confirm=True)
        latest = subscription.invoices.order_by('-period_start').first()
        self.assertEqual((latest.period_start, latest.tax_total), (next_period, Decimal('50.00')))

    def test_a_tax_rate_typed_on_a_line_overrides_the_rules(self):
        TaxRule.objects.create(name='GST', rate=18)
        subscription = self.make_subscription(self.alice, 'draft')
        SubscriptionLine.objects.filter(subscription=subscription).update(tax_rate=Decimal('0.00'))
        services.confirm(subscription, self.staff)
        self.assertEqual(subscription.invoices.get().tax_total, Decimal('0.00'))

    def test_only_the_admin_changes_tax_rules_and_they_are_validated(self):
        payload = {'name': 'GST', 'rate': '18.00'}
        self.assertEqual(self.staff_api.post('/api/tax-rules/', payload, format='json').status_code, 403)
        self.assertEqual(self.staff_api.get('/api/tax-rules/').status_code, 200)
        self.assertEqual(self.admin_api.post('/api/tax-rules/', payload, format='json').status_code, 201)
        for label, bad in {
            'rate above 100': {'name': 'x', 'rate': '101.00'},
            'negative rate': {'name': 'x', 'rate': '-1.00'},
            'product and type together': {'name': 'x', 'rate': '5', 'product': self.product.id, 'product_type': 'service'},
        }.items():
            with self.subTest(label):
                self.assertEqual(self.admin_api.post('/api/tax-rules/', bad, format='json').status_code, 400)

    def test_quotation_and_catalogue_show_the_same_rate_the_invoice_will_use(self):
        TaxRule.objects.create(name='Services', rate=12, product_type='service')
        row = next(p for p in self.staff_api.get('/api/catalog/products/').json() if p['id'] == self.product.id)
        self.assertEqual(float(row['default_tax_rate']), 12.0)
        subscription = self.activate(self.alice)
        self.assertEqual(subscription.invoices.get().lines.get().tax_rate, Decimal('12.00'))


# ====================================================================================== discounts


class DiscountTests(FlowCase):
    def discount(self, **overrides):
        values = dict(name='Promo', kind='percentage', value=10, applies_to='subscription', start_date=days_ago(1))
        values.update(overrides)
        discount = Discount.objects.create(**values)
        return discount

    def invoice_for(self, customer, lines=None):
        return self.activate(customer, lines=lines).invoices.get()

    def test_a_percentage_discount_lands_on_the_invoice_by_itself(self):
        self.discount()
        invoice = self.invoice_for(self.alice, [(self.product, 3, 1000)])
        self.assertEqual((invoice.subtotal, invoice.discount_total, invoice.amount), (Decimal('3000.00'), Decimal('300.00'), Decimal('2700.00')))
        self.assertEqual([(d.name, d.amount) for d in invoice.discounts.all()], [('Promo', Decimal('300.00'))])

    def test_a_fixed_discount_takes_a_fixed_amount_and_never_more_than_the_bill(self):
        self.discount(kind='fixed', value=100)
        self.assertEqual(self.invoice_for(self.alice).amount, Decimal('900.00'))
        Discount.objects.all().delete()
        self.discount(kind='fixed', value=5000)
        invoice = self.invoice_for(self.bob)
        self.assertEqual((invoice.discount_total, invoice.amount), (Decimal('1000.00'), Decimal('0.00')))

    def test_a_product_discount_only_touches_matching_lines(self):
        other = Product.objects.create(name='Support', product_type='service', sales_price=200, cost_price=50)
        discount = self.discount(value=50, applies_to='products')
        discount.products.set([self.product])
        invoice = self.invoice_for(self.alice, [(self.product, 1, 100), (other, 1, 200)])
        by_product = {l.description.split(',')[0]: l.discount_amount for l in invoice.lines.all()}
        self.assertEqual(by_product, {'CRM': Decimal('50.00'), 'Support': Decimal('0.00')})
        self.assertEqual(invoice.discount_total, Decimal('50.00'))

    def test_a_product_discount_with_no_matching_product_does_nothing(self):
        other = Product.objects.create(name='Support', product_type='service', sales_price=200, cost_price=50)
        discount = self.discount(applies_to='products')
        discount.products.set([other])
        invoice = self.invoice_for(self.alice)
        self.assertEqual(invoice.discount_total, Decimal('0.00'))
        discount.refresh_from_db()
        self.assertEqual(discount.times_used, 0)

    def test_a_subscription_discount_is_shared_across_every_line(self):
        other = Product.objects.create(name='Support', product_type='service', sales_price=200, cost_price=50)
        self.discount(value=10)
        invoice = self.invoice_for(self.alice, [(self.product, 1, 100), (other, 1, 200)])
        by_product = {l.description.split(',')[0]: l.discount_amount for l in invoice.lines.all()}
        self.assertEqual(by_product, {'CRM': Decimal('10.00'), 'Support': Decimal('20.00')})
        self.assertEqual(invoice.discount_total, Decimal('30.00'))

    def test_discount_tax_is_charged_on_the_discounted_amount(self):
        TaxRule.objects.create(name='GST', rate=18)
        self.discount(value=10)
        invoice = self.invoice_for(self.alice, [(self.product, 1, 1000)])
        self.assertEqual((invoice.subtotal, invoice.discount_total, invoice.tax_total, invoice.amount), (
            Decimal('1000.00'), Decimal('100.00'), Decimal('162.00'), Decimal('1062.00'),
        ))

    def test_minimum_purchase_decides_who_qualifies(self):
        self.discount(min_purchase=500)
        small = self.invoice_for(self.alice, [(self.product, 1, 300)])
        big = self.invoice_for(self.bob, [(self.product, 1, 600)])
        self.assertEqual((small.discount_total, big.discount_total), (Decimal('0.00'), Decimal('60.00')))
        self.assertEqual(Discount.objects.get().times_used, 1)

    def test_minimum_quantity_decides_who_qualifies(self):
        self.discount(min_quantity=3)
        two = self.invoice_for(self.alice, [(self.product, 2, 100)])
        three = self.invoice_for(self.bob, [(self.product, 3, 100)])
        self.assertEqual((two.discount_total, three.discount_total), (Decimal('0.00'), Decimal('30.00')))

    def test_the_minimum_quantity_of_a_product_discount_counts_only_matching_lines(self):
        other = Product.objects.create(name='Support', product_type='service', sales_price=200, cost_price=50)
        discount = self.discount(applies_to='products', min_quantity=3)
        discount.products.set([self.product])
        invoice = self.invoice_for(self.alice, [(self.product, 2, 100), (other, 5, 100)])
        self.assertEqual(invoice.discount_total, Decimal('0.00'))

    def test_only_discounts_inside_their_dates_apply(self):
        self.discount(name='Future', start_date=TODAY + timedelta(days=1))
        self.discount(name='Past', start_date=days_ago(10), end_date=days_ago(1))
        self.discount(name='Disabled', is_active=False)
        self.assertEqual(self.invoice_for(self.alice).discount_total, Decimal('0.00'))
        self.discount(name='Open', start_date=TODAY, end_date=TODAY)
        self.assertEqual(self.invoice_for(self.bob).discount_total, Decimal('100.00'))
        self.assertEqual([d.name for d in Invoice.objects.latest('id').discounts.all()], ['Open'])

    def test_a_usage_limit_stops_the_discount_after_that_many_uses(self):
        self.discount(usage_limit=2)
        carol = User.objects.create_user('carol', 'carol@example.com', 'Carol#Pass12', role='customer')
        results = [self.invoice_for(customer).discount_total for customer in (self.alice, self.bob, carol)]
        self.assertEqual(results, [Decimal('100.00'), Decimal('100.00'), Decimal('0.00')])
        discount = Discount.objects.get()
        self.assertEqual(discount.times_used, 2)
        self.assertEqual(discount.status, 'exhausted')

    def test_two_discounts_together_never_push_a_line_below_zero(self):
        self.discount(name='A', kind='fixed', value=80)
        self.discount(name='B', kind='fixed', value=80)
        invoice = self.invoice_for(self.alice, [(self.product, 1, 100)])
        line = invoice.lines.get()
        self.assertEqual(line.discount_amount, Decimal('100.00'))
        self.assertEqual((invoice.discount_total, invoice.amount), (Decimal('100.00'), Decimal('0.00')))
        self.assertEqual(sum(d.amount for d in invoice.discounts.all()), Decimal('100.00'))

    def test_stacked_percentages_apply_to_what_is_left(self):
        self.discount(name='A', value=60)
        self.discount(name='B', value=60)
        invoice = self.invoice_for(self.alice, [(self.product, 1, 100)])
        self.assertEqual(invoice.discount_total, Decimal('84.00'))
        self.assertGreaterEqual(invoice.amount, 0)

    def test_a_discount_appears_on_the_next_invoice_then_stops_when_it_expires(self):
        subscription = self.activate(self.alice)
        self.assertEqual(subscription.invoices.get().discount_total, Decimal('0.00'))
        second_start = subscription.next_billing_date
        third_start = self.plan.next_billing_after(second_start, subscription.start_date)
        self.discount(start_date=TODAY, end_date=third_start - timedelta(days=1))
        run_billing(as_of=second_start, actor=self.staff, confirm=True)
        run_billing(as_of=third_start, actor=self.staff, confirm=True)
        totals = {i.period_start: i.discount_total for i in subscription.invoices.all()}
        self.assertEqual(totals[second_start], Decimal('100.00'))
        self.assertEqual(totals[third_start], Decimal('0.00'))

    def test_only_the_admin_creates_discounts_and_the_rules_are_validated(self):
        payload = {'name': 'D', 'kind': 'percentage', 'value': '10', 'applies_to': 'subscription', 'start_date': str(TODAY)}
        self.assertEqual(self.staff_api.post('/api/discounts/', payload, format='json').status_code, 403)
        self.assertEqual(self.alice_api.get('/api/discounts/').status_code, 403)
        self.assertEqual(self.admin_api.post('/api/discounts/', payload, format='json').status_code, 201)
        bad_cases = {
            'percentage above 100': {**payload, 'value': '150'},
            'zero value': {**payload, 'value': '0'},
            'negative value': {**payload, 'kind': 'fixed', 'value': '-5'},
            'end before start': {**payload, 'end_date': str(TODAY - timedelta(days=1))},
        }
        for label, bad in bad_cases.items():
            with self.subTest(label):
                self.assertEqual(self.admin_api.post('/api/discounts/', bad, format='json').status_code, 400)

    def test_a_product_discount_needs_products(self):
        payload = {'name': 'D', 'kind': 'percentage', 'value': '10', 'applies_to': 'products', 'start_date': str(TODAY)}
        response = self.admin_api.post('/api/discounts/', payload, format='json')
        self.assertEqual(response.status_code, 400, 'a product discount with no products was saved and can never apply')

    def test_discount_status_reflects_its_dates_and_usage(self):
        self.assertEqual(self.discount(name='a').status, 'active')
        self.assertEqual(self.discount(name='b', start_date=TODAY + timedelta(days=2)).status, 'scheduled')
        self.assertEqual(self.discount(name='c', end_date=days_ago(0) - timedelta(days=1)).status, 'expired')
        self.assertEqual(self.discount(name='d', is_active=False).status, 'disabled')
        self.assertEqual(self.discount(name='e', usage_limit=1, times_used=1).status, 'exhausted')


# ====================================================================================== invoices and payments


class InvoiceWorkflowTests(FlowCase):
    def setUp(self):
        super().setUp()
        self.subscription = self.activate(self.alice)
        self.confirmed = self.subscription.invoices.get()
        self.draft = build_invoice(self.subscription, days_ago(31), actor=self.staff)

    def pay(self, invoice, amount, **extra):
        payload = {'invoice': invoice.id, 'amount': str(amount), 'method': 'bank_transfer', **extra}
        return self.staff_api.post('/api/payments/', payload, format='json')

    def action(self, invoice, name, client=None):
        return (client or self.staff_api).post(f'/api/invoices/{invoice.id}/{name}/')

    def test_draft_to_confirmed_to_paid(self):
        self.assertEqual(self.draft.status, 'draft')
        self.assertEqual(self.action(self.draft, 'confirm').json()['status'], 'confirmed')
        response = self.pay(self.draft, self.draft.amount, note='Ref 42')
        self.assertEqual(response.status_code, 201, response.content)
        detail = self.staff_api.get(f'/api/invoices/{self.draft.id}/').json()
        self.assertEqual((detail['status'], detail['balance'], detail['amount_paid']), ('paid', '0.00', '1000.00'))
        self.assertEqual(detail['payments'][0]['note'], 'Ref 42')
        self.assertEqual(detail['payments'][0]['method'], 'bank_transfer')

    def test_payments_need_a_confirmed_invoice(self):
        self.assertEqual(self.pay(self.draft, 100).status_code, 400)
        self.action(self.draft, 'cancel')
        self.assertEqual(self.pay(self.draft, 100).status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_amounts_must_be_positive_and_not_above_the_balance(self):
        for label, amount in {'zero': '0', 'negative': '-5', 'above balance': '1000.01'}.items():
            with self.subTest(label):
                self.assertEqual(self.pay(self.confirmed, amount).status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_method_and_dates_are_validated(self):
        self.assertEqual(self.pay(self.confirmed, 10, method='bitcoin').status_code, 400)
        self.assertEqual(self.pay(self.confirmed, 10, paid_on=str(TODAY + timedelta(days=1))).status_code, 400)
        self.assertEqual(self.pay(self.confirmed, 10, paid_on=str(self.confirmed.issue_date - timedelta(days=1))).status_code, 400)
        self.assertEqual(self.pay(self.confirmed, 10, paid_on=str(TODAY), method='cheque').status_code, 201)

    def test_partial_payments_keep_the_invoice_confirmed_until_it_is_settled(self):
        self.assertEqual(self.pay(self.confirmed, 400).status_code, 201)
        detail = self.staff_api.get(f'/api/invoices/{self.confirmed.id}/').json()
        self.assertEqual((detail['status'], detail['balance']), ('confirmed', '600.00'))
        self.assertEqual(self.pay(self.confirmed, 700).status_code, 400)
        self.assertEqual(self.pay(self.confirmed, 600).status_code, 201)
        self.assertEqual(self.staff_api.get(f'/api/invoices/{self.confirmed.id}/').json()['status'], 'paid')
        self.assertEqual(self.pay(self.confirmed, 1).status_code, 400)

    def test_cancel_is_allowed_on_drafts_and_unpaid_confirmed_invoices_only(self):
        self.assertEqual(self.action(self.draft, 'cancel').json()['status'], 'cancelled')
        self.assertEqual(self.action(self.draft, 'confirm').status_code, 400)
        self.assertEqual(self.action(self.confirmed, 'cancel').json()['status'], 'cancelled')

        paid_part = build_invoice(self.subscription, days_ago(62), actor=self.staff, confirm=True)
        self.pay(paid_part, 100)
        self.assertEqual(self.action(paid_part, 'cancel').status_code, 400)
        self.assertEqual(self.staff_api.get(f'/api/invoices/{paid_part.id}/').json()['status'], 'confirmed')

        settled = build_invoice(self.subscription, days_ago(93), actor=self.staff, confirm=True)
        self.pay(settled, settled.amount)
        self.assertEqual(self.action(settled, 'cancel').status_code, 400)

    def test_send_emails_the_customer_and_remind_only_works_when_overdue(self):
        self.assertEqual(self.action(self.draft, 'send').status_code, 400)
        self.assertEqual(len(mail.outbox), 0)
        sent = self.action(self.confirmed, 'send')
        self.assertEqual(sent.status_code, 200)
        self.assertIsNotNone(sent.json()['sent_at'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['alice@example.com'])
        self.assertIn(self.confirmed.number, mail.outbox[0].subject)

        self.assertEqual(self.action(self.confirmed, 'remind').status_code, 400)
        self.assertEqual(len(mail.outbox), 1)
        self.action(self.draft, 'confirm')
        reminded = self.action(self.draft, 'remind')
        self.assertEqual(reminded.status_code, 200, reminded.content)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('overdue', mail.outbox[1].subject.lower())
        self.assertIsNotNone(reminded.json()['last_reminder_at'])

    def test_a_paid_invoice_can_be_sent_but_not_reminded(self):
        self.pay(self.confirmed, self.confirmed.amount)
        self.assertEqual(self.action(self.confirmed, 'send').status_code, 200)
        self.assertEqual(self.action(self.confirmed, 'remind').status_code, 400)

    def test_only_staff_can_confirm_cancel_send_or_remind(self):
        for name in ('confirm', 'cancel', 'send', 'remind'):
            self.assertEqual(self.action(self.confirmed, name, self.alice_api).status_code, 403, name)

    def test_the_customer_pay_action_settles_the_whole_remaining_balance(self):
        self.pay(self.confirmed, 300)
        response = self.action(self.confirmed, 'pay', self.alice_api)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['status'], response.json()['balance']), ('paid', '0.00'))
        last = Payment.objects.order_by('-id').first()
        self.assertEqual((last.amount, last.method, last.note), (Decimal('700.00'), 'card', 'Paid online (demo gateway)'))
        self.assertEqual(self.action(self.confirmed, 'pay', self.alice_api).status_code, 400)

    def test_a_customer_cannot_pay_a_draft_or_someone_elses_invoice(self):
        self.assertEqual(self.action(self.draft, 'pay', self.alice_api).status_code, 404)
        self.assertEqual(self.action(self.confirmed, 'pay', self.bob_api).status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)

    def test_payments_are_listed_and_filterable_for_the_team(self):
        self.pay(self.confirmed, 100, method='cash')
        self.pay(self.confirmed, 50, method='upi')
        rows = self.staff_api.get('/api/payments/').json()
        self.assertEqual(rows['count'], 2)
        self.assertEqual(self.staff_api.get('/api/payments/?method=cash').json()['count'], 1)
        self.assertEqual(self.staff_api.get(f'/api/payments/?invoice={self.confirmed.id}').json()['count'], 2)
        self.assertEqual(self.staff_api.get('/api/payments/?q=alice').json()['count'], 2)
        self.assertEqual(self.staff_api.get('/api/payments/?q=nobody').json()['count'], 0)

    def test_invoice_list_filters_find_paid_outstanding_and_overdue(self):
        self.action(self.draft, 'confirm')
        paid = build_invoice(self.subscription, days_ago(62), actor=self.staff, confirm=True)
        self.pay(paid, paid.amount)
        ids = lambda query: {i['id'] for i in self.staff_api.get(f'/api/invoices/{query}').json()['results']}
        self.assertEqual(ids('?status=paid'), {paid.id})
        self.assertEqual(ids('?status=confirmed'), {self.confirmed.id, self.draft.id})
        self.assertEqual(ids('?overdue=1'), {self.draft.id})
        self.assertEqual(ids(f'?q={self.confirmed.number}'), {self.confirmed.id})
        self.assertEqual(ids(f'?customer={self.bob.id}'), set())


# ====================================================================================== reporting


class ReportingCase(FlowCase):
    """A small dataset with known answers: 3 live subscriptions, one paused, one closed, 4 invoices, 3 payments."""

    def setUp(self):
        super().setUp()
        self.carol = User.objects.create_user('carol', 'carol@example.com', 'Carol#Pass12', role='customer')
        self.dave = User.objects.create_user('dave', 'dave@example.com', 'Dave#Pass123', role='customer')
        self.erin = User.objects.create_user('erin', 'erin@example.com', 'Erin#Pass123', role='customer')
        self.weekly = self.make_plan(name='Weekly', price=100, billing_frequency='weekly')
        self.monthly = self.plan
        self.yearly = self.make_plan(name='Yearly', price=12000, billing_frequency='yearly')
        p = self.product
        self.s1 = self.make_subscription(self.alice, 'active', self.weekly, [(p, 2, 100)], start=days_ago(50), next_billing=TODAY)
        self.s2 = self.make_subscription(self.bob, 'active', self.monthly, [(p, 3, 1000)], start=days_ago(20), next_billing=TODAY + timedelta(days=10))
        self.s3 = self.make_subscription(self.carol, 'active', self.yearly, [(p, 1, 12000)], start=days_ago(10), next_billing=TODAY + timedelta(days=20))
        self.s4 = self.make_subscription(self.dave, 'paused', self.monthly, [(p, 1, 1000)], start=days_ago(40), next_billing=TODAY + timedelta(days=3))
        self.s5 = self.make_subscription(self.erin, 'closed', self.monthly, [(p, 1, 1000)], start=days_ago(100), end_date=days_ago(10))

        self.i1 = self.invoice(self.s2, 'confirmed', 3540, issued=40, due=-25)
        self.i2 = self.invoice(self.s3, 'confirmed', 14160, issued=5, due=10)
        self.i3 = self.invoice(self.s1, 'paid', 236, issued=20, due=-5)
        self.i4 = self.invoice(self.s2, 'confirmed', 3540, issued=70, due=-55)
        self.pay(self.i2, 5000, 2, 'bank_transfer')
        self.pay(self.i3, 236, 15, 'card')
        self.pay(self.i4, 1000, 60, 'cash')

    def invoice(self, subscription, status, amount, issued, due):
        invoice = Invoice.objects.create(
            customer=subscription.customer, subscription=subscription, status=status, issue_date=days_ago(issued),
            due_date=TODAY + timedelta(days=due), subtotal=amount, amount=amount,
            created_by=self.staff,
        )
        InvoiceLine.objects.create(invoice=invoice, description='Charge', quantity=1, unit_price=amount, tax_rate=0)
        return invoice

    def pay(self, invoice, amount, ago, method):
        return Payment.objects.create(invoice=invoice, amount=amount, paid_on=days_ago(ago), method=method, recorded_by=self.staff)

    def report(self, query=''):
        response = self.staff_api.get(f'/api/dashboard/reports/{query}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def assertMoney(self, actual, expected, label=''):
        self.assertAlmostEqual(float(actual), float(expected), places=2, msg=label)


class ReportTests(ReportingCase):
    def test_active_subscriptions_and_mrr_use_each_plans_billing_frequency(self):
        summary = self.report()['summary']
        self.assertEqual((summary['active_subscriptions'], summary['total_subscriptions']), (3, 5))
        expected_mrr = (Decimal(200) * Decimal(52) / 12 + Decimal(3000) + Decimal(12000) / 12).quantize(Decimal('0.01'))
        self.assertEqual(expected_mrr, Decimal('4866.67'))
        self.assertMoney(summary['mrr'], expected_mrr)
        self.assertMoney(summary['arr'], expected_mrr * 12)

    def test_revenue_by_plan_counts_only_active_subscriptions(self):
        rows = {r['plan']: r for r in self.report()['plans']}
        self.assertMoney(rows['Weekly']['mrr'], Decimal('866.67'))
        self.assertMoney(rows['Monthly']['mrr'], 3000)
        self.assertMoney(rows['Yearly']['mrr'], 1000)
        self.assertEqual(rows['Monthly']['active_subscriptions'], 1)

    def test_all_time_revenue_outstanding_and_overdue(self):
        summary = self.report()['summary']
        self.assertMoney(summary['revenue'], 6236)
        self.assertEqual(summary['payments_count'], 3)
        self.assertMoney(summary['invoiced'], 21476)
        self.assertEqual((summary['outstanding']['count'], round(float(summary['outstanding']['amount']), 2)), (3, 15240.0))
        self.assertEqual((summary['overdue']['count'], round(float(summary['overdue']['amount']), 2)), (2, 6080.0))
        self.assertEqual(summary['collection_rate'], round(6236 / 21476 * 100, 1))

    def test_a_date_window_filters_revenue_payments_and_invoicing(self):
        window = f'?from={days_ago(30)}&to={TODAY}'
        summary = self.report(window)['summary']
        self.assertMoney(summary['revenue'], 5236)
        self.assertEqual(summary['payments_count'], 2)
        self.assertMoney(summary['invoiced'], 14396)
        self.assertEqual(summary['collection_rate'], round(5236 / 14396 * 100, 1))
        self.assertEqual(summary['new_subscriptions'], 2)
        self.assertEqual(summary['closed_subscriptions'], 1)

    def test_a_plan_filter_narrows_everything_to_that_plan(self):
        summary = self.report(f'?plan={self.weekly.id}')['summary']
        self.assertEqual((summary['active_subscriptions'], summary['total_subscriptions']), (1, 1))
        self.assertMoney(summary['revenue'], 236)
        self.assertMoney(summary['invoiced'], 236)
        self.assertEqual(summary['collection_rate'], 100.0)

    def test_overdue_aging_buckets_and_the_chase_list(self):
        report = self.report()
        buckets = {row['label']: float(row['amount']) for row in report['invoice_aging']}
        self.assertEqual(buckets, {'Not yet due': 9160.0, '1-30 days': 3540.0, '31-60 days': 2540.0, '60+ days': 0.0})
        chase = report['overdue_invoices']
        self.assertEqual([r['number'] for r in chase], [self.i4.number, self.i1.number])
        self.assertEqual([r['days_overdue'] for r in chase], [55, 25])
        self.assertEqual([round(float(r['balance']), 2) for r in chase], [2540.0, 3540.0])

    def test_payment_methods_and_statuses_add_up(self):
        report = self.report()
        methods = {m['method']: float(m['amount']) for m in report['payment_methods']}
        self.assertEqual(methods, {'bank_transfer': 5000.0, 'card': 236.0, 'cash': 1000.0})
        counts = {s['status']: s['count'] for s in report['status_breakdown']}
        self.assertEqual((counts['active'], counts['paused'], counts['closed'], counts['draft']), (3, 1, 1, 0))
        invoices = {s['status']: s['count'] for s in report['invoice_breakdown']}
        self.assertEqual((invoices['paid'], invoices['overdue'], invoices['confirmed']), (1, 2, 1))

    def test_the_forecast_counts_billings_due_in_the_next_30_days(self):
        forecast = self.report()['billing_forecast_30d']
        self.assertEqual(forecast['count'], 3)
        self.assertMoney(forecast['amount'], 200 + 3000 + 12000)

    def test_revenue_by_month_matches_the_payments(self):
        months = self.report()['revenue_by_month']
        self.assertEqual(len(months), 12)
        self.assertMoney(sum(float(m['revenue']) for m in months), 6236)

    def test_customers_cannot_read_reports(self):
        self.assertEqual(self.alice_api.get('/api/dashboard/reports/').status_code, 403)


class DashboardTests(ReportingCase):
    def test_the_admin_dashboard_matches_the_database(self):
        Quotation.objects.create(customer=self.alice, status='draft', created_by=self.staff)
        body = self.admin_api.get('/api/dashboard/admin/').json()
        stats = body['stats']
        self.assertEqual((stats['total_customers'], stats['total_staff'], stats['total_products']), (5, 1, 1))
        self.assertEqual(stats['active_subscriptions'], 3)
        self.assertMoney(stats['monthly_recurring_revenue'], Decimal('4866.67'))
        self.assertMoney(stats['annual_recurring_revenue'], Decimal('4866.67') * 12)
        self.assertMoney(stats['total_revenue'], 6236)
        self.assertEqual((stats['outstanding_invoices']['count'], round(float(stats['outstanding_invoices']['amount']), 2)), (3, 15240.0))
        self.assertEqual((stats['overdue_invoices']['count'], round(float(stats['overdue_invoices']['amount']), 2)), (2, 6080.0))

        month_start = TODAY.replace(day=1)
        payments = [(5000, 2), (236, 15), (1000, 60)]
        this_month = sum(a for a, ago in payments if days_ago(ago) >= month_start)
        self.assertMoney(stats['revenue_this_month'], this_month)
        self.assertMoney(stats['collection']['collected'], this_month)
        invoices = [(14160, 5), (236, 20), (3540, 40), (3540, 70)]
        self.assertMoney(stats['collection']['billed'], sum(a for a, ago in invoices if days_ago(ago) >= month_start))
        self.assertMoney(body['revenue_by_month'][-1]['revenue'], this_month)
        self.assertEqual(
            sorted(body),
            sorted([
                'stats', 'revenue_by_month', 'mrr_movement', 'subscription_growth', 'status_breakdown', 'invoice_breakdown',
                'payment_methods', 'overdue_invoices', 'recent_customers', 'recent_subscriptions', 'recent_invoices', 'recent_payments',
            ]),
        )
        self.assertEqual((len(body['revenue_by_month']), len(body['mrr_movement']), len(body['subscription_growth'])), (6, 6, 6))
        self.assertEqual(len(body['recent_payments']), 3)
        self.assertEqual(len(body['recent_customers']), 5)

    def test_the_staff_dashboard_matches_the_database(self):
        Quotation.objects.create(customer=self.alice, status='draft', created_by=self.staff)
        Quotation.objects.create(customer=self.alice, status='sent', created_by=self.staff)
        Quotation.objects.create(customer=self.bob, status='accepted', created_by=self.staff)
        build_invoice(self.s1, days_ago(40), actor=self.staff)
        body = self.staff_api.get('/api/dashboard/staff/').json()
        stats = body['stats']
        self.assertEqual(stats['assigned_customers'], 2)
        self.assertEqual((stats['total_quotations'], stats['pending_quotations']), (3, 2))
        self.assertEqual(stats['active_subscriptions'], 3)
        self.assertEqual((stats['pending_invoices']['count'], round(float(stats['pending_invoices']['amount']), 2)), (3, 15240.0))
        self.assertEqual((stats['overdue_invoices']['count'], round(float(stats['overdue_invoices']['amount']), 2)), (2, 6080.0))
        self.assertEqual((stats['draft_invoices'], stats['due_for_billing']), (1, 1))
        for key in ('recent_activities', 'quotations_awaiting_action', 'recent_subscriptions', 'invoices_awaiting_payment', 'overdue_invoices', 'upcoming_renewals'):
            self.assertIn(key, body)
        self.assertEqual(len(body['quotations_awaiting_action']), 2)
        self.assertEqual(len(body['invoices_awaiting_payment']), 3)
        renewals = {r['number'] for r in body['upcoming_renewals']}
        self.assertEqual(renewals, {self.s1.number, self.s2.number, self.s3.number})

    def test_the_customer_dashboard_shows_only_their_own_figures(self):
        build_invoice(self.s1, days_ago(40), actor=self.staff)
        alice = self.alice_api.get('/api/dashboard/customer/').json()
        self.assertEqual(alice['stats']['active_subscriptions'], 1)
        self.assertEqual((alice['stats']['total_invoices'], alice['stats']['paid_invoices']), (1, 1))
        self.assertEqual((alice['stats']['pending_payments']['count'], float(alice['stats']['pending_payments']['amount'])), (0, 0.0))
        self.assertEqual(alice['active_subscription']['number'], self.s1.number)
        self.assertEqual(alice['next_billing_date'], str(TODAY))
        self.assertEqual(alice['days_to_renewal'], 365)
        self.assertEqual(len(alice['payment_history']), 1)

        bob = self.bob_api.get('/api/dashboard/customer/').json()
        self.assertEqual((bob['stats']['total_invoices'], bob['stats']['paid_invoices']), (2, 0))
        self.assertEqual((bob['stats']['pending_payments']['count'], round(float(bob['stats']['pending_payments']['amount']), 2)), (2, 6080.0))
        self.assertEqual((bob['stats']['overdue_payments']['count'], round(float(bob['stats']['overdue_payments']['amount']), 2)), (2, 6080.0))
        self.assertNotIn(self.s1.number, str(bob))
        for key in ('available_plans', 'recent_invoices', 'payment_history', 'next_billing_amount'):
            self.assertIn(key, bob)

    def test_a_customer_with_nothing_still_gets_a_valid_dashboard(self):
        newbie = User.objects.create_user('newbie', 'newbie@example.com', 'Newbie#Pass1', role='customer')
        body = self.api(newbie).get('/api/dashboard/customer/').json()
        self.assertIsNone(body['active_subscription'])
        self.assertEqual(body['stats']['total_invoices'], 0)
        self.assertGreaterEqual(len(body['available_plans']), 1)

    def test_search_finds_records_and_keeps_customers_to_their_own(self):
        found = self.staff_api.get('/api/search/?q=bob').json()['results']
        self.assertIn('customer', {r['type'] for r in found})
        mine = self.alice_api.get(f'/api/search/?q={self.s2.number}').json()['results']
        self.assertEqual(mine, [], 'a customer found someone elses subscription')
        own = self.alice_api.get(f'/api/search/?q={self.s1.number}').json()['results']
        self.assertEqual([r['title'] for r in own], [self.s1.number])
        self.assertEqual(self.staff_api.get('/api/search/?q=a').json()['results'], [])
