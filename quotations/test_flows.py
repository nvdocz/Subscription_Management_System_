"""PDF story: turning a quote into a subscription, from templates to the customer's own plan requests."""

import re
from datetime import date, timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from billing.models import Invoice
from plans.models import SubscriptionPlan
from pricing.models import TaxRule
from products.models import Product
from quotations.models import Quotation
from subscriptions.models import Subscription

FAST = dict(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
TODAY = timezone.localdate()


@override_settings(**FAST)
class QuoteFlowCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('boss', 'boss@example.com', 'Boss#Pass123', role='admin')
        self.staff = User.objects.create_user('rep', 'rep@example.com', 'Rep#Pass1234', role='staff')
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'Alice#Pass12', role='customer')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'Bob#Pass1234', role='customer')
        self.product = Product.objects.create(name='CRM', product_type='service', sales_price=1000, cost_price=400)
        self.basic = self.make_plan('Basic', 499)
        self.pro = self.make_plan('Professional', 999)
        self.enterprise = self.make_plan('Enterprise', 9999, 'yearly')
        TaxRule.objects.create(name='GST', rate=18)
        self.staff_api = self.api(self.staff)
        self.alice_api = self.api(self.alice)
        self.bob_api = self.api(self.bob)

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def make_plan(self, name, price, frequency='monthly', **extra):
        return SubscriptionPlan.objects.create(
            product=self.product, name=name, price=price, billing_frequency=frequency,
            start_date=TODAY - timedelta(days=30), **extra,
        )

    def items(self, quantity=2, price='999.00', tax='18.00'):
        return [{'product': self.product.id, 'quantity': quantity, 'unit_price': price, 'tax_rate': tax}]

    def create_quotation(self, customer=None, plan='basic', **overrides):
        payload = {
            'customer': (customer or self.alice).id,
            'plan': getattr(self, plan).id if isinstance(plan, str) else (plan.id if plan else None),
            'validity_days': 15,
            'payment_terms': 'net_30',
            'notes': 'Offer',
            'items': self.items(),
        }
        payload.update(overrides)
        return self.staff_api.post('/api/quotations/', payload, format='json')

    def sent_quotation(self, **kwargs):
        quotation = self.create_quotation(**kwargs).json()
        self.assertEqual(self.staff_api.post(f'/api/quotations/{quotation["id"]}/send/').status_code, 200)
        return quotation

    def request_plan(self, client, plan):
        return client.post(f'/api/catalog/plans/{plan.id}/request/')


class TemplateTests(QuoteFlowCase):
    def template_payload(self, **overrides):
        payload = {'name': 'Standard CRM', 'plan': self.pro.id, 'notes': 'Default bundle', 'items': self.items()}
        payload.update(overrides)
        return payload

    def test_template_create_read_update_delete(self):
        created = self.staff_api.post('/api/quotation-templates/', self.template_payload(), format='json')
        self.assertEqual(created.status_code, 201, created.content)
        template = created.json()
        self.assertEqual(template['plan'], self.pro.id)
        self.assertEqual(len(template['items']), 1)
        self.assertEqual(self.staff_api.get(f'/api/quotation-templates/{template["id"]}/').json()['name'], 'Standard CRM')

        renamed = self.staff_api.patch(f'/api/quotation-templates/{template["id"]}/', {'name': 'Renamed'}, format='json')
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(len(renamed.json()['items']), 1, 'renaming must keep the lines')

        replaced = self.staff_api.patch(
            f'/api/quotation-templates/{template["id"]}/', {'items': self.items(quantity=5, price='50.00')}, format='json'
        )
        self.assertEqual([i['quantity'] for i in replaced.json()['items']], [5])

        self.assertEqual(self.staff_api.delete(f'/api/quotation-templates/{template["id"]}/').status_code, 204)
        self.assertEqual(self.staff_api.get('/api/quotation-templates/').json(), [])

    def test_a_template_needs_at_least_one_line_and_is_staff_only(self):
        self.assertEqual(self.staff_api.post('/api/quotation-templates/', self.template_payload(items=[]), format='json').status_code, 400)
        self.assertEqual(self.alice_api.post('/api/quotation-templates/', self.template_payload(), format='json').status_code, 403)
        self.assertEqual(self.alice_api.get('/api/quotation-templates/').status_code, 403)

    def test_a_quotation_built_from_a_template_carries_the_same_lines_and_stays_valid_15_days(self):
        template = self.staff_api.post('/api/quotation-templates/', self.template_payload(), format='json').json()
        payload = {
            'customer': self.alice.id,
            'plan': template['plan'],
            'validity_days': 15,
            'items': [
                {k: item[k] for k in ('product', 'quantity', 'unit_price', 'tax_rate')} for item in template['items']
            ],
        }
        response = self.staff_api.post('/api/quotations/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body['status'], 'draft')
        issued = date.fromisoformat(body['issued_date'])
        self.assertEqual(date.fromisoformat(body['valid_until']) - issued, timedelta(days=15))
        self.assertEqual((body['subtotal'], body['tax_total'], body['total']), ('1998.00', '359.64', '2357.64'))
        self.assertEqual(body['plan_detail']['name'], 'Professional')

    def test_validity_is_whatever_the_rep_sets(self):
        body = self.create_quotation(validity_days=30).json()
        self.assertEqual(date.fromisoformat(body['valid_until']) - date.fromisoformat(body['issued_date']), timedelta(days=30))


class QuotationStatusTests(QuoteFlowCase):
    def test_draft_send_accept_convert_creates_an_active_numbered_subscription_and_first_invoice(self):
        quotation = self.create_quotation(plan='pro').json()
        self.assertEqual(quotation['status'], 'draft')
        self.assertEqual(self.staff_api.post(f'/api/quotations/{quotation["id"]}/send/').json()['status'], 'sent')
        accepted = self.alice_api.post(f'/api/quotations/{quotation["id"]}/accept/')
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()['status'], 'accepted')
        self.assertIsNone(accepted.json()['subscription'], 'a rep-made quotation waits for the rep to convert it')

        converted = self.staff_api.post(f'/api/quotations/{quotation["id"]}/convert/')
        self.assertEqual(converted.status_code, 200, converted.content)
        subscription_id = converted.json()['subscription']
        self.assertIsNotNone(subscription_id)

        subscription = self.staff_api.get(f'/api/subscriptions/{subscription_id}/').json()
        self.assertRegex(subscription['number'], r'^SUB-\d{5}$')
        self.assertEqual(subscription['status'], 'active')
        self.assertEqual(subscription['customer'], self.alice.id)
        self.assertEqual(subscription['plan'], self.pro.id)
        self.assertEqual(subscription['payment_terms'], 'net_30')
        self.assertEqual(len(subscription['lines']), 1)
        line = subscription['lines'][0]
        self.assertEqual((line['product'], line['quantity'], line['unit_price'], line['tax_rate']), (self.product.id, 2, '999.00', '18.00'))

        invoices = list(Invoice.objects.filter(subscription_id=subscription_id))
        self.assertEqual(len(invoices), 1)
        invoice = invoices[0]
        self.assertEqual(invoice.status, 'confirmed')
        self.assertEqual((invoice.subtotal, invoice.tax_total, invoice.amount), (Decimal('1998.00'), Decimal('359.64'), Decimal('2357.64')))
        self.assertEqual(invoice.due_date - invoice.issue_date, timedelta(days=30))
        self.assertEqual(invoice.customer_id, self.alice.id)

    def test_a_draft_quotation_cannot_be_accepted_and_the_customer_cannot_even_see_it(self):
        quotation = self.create_quotation().json()
        self.assertEqual(self.alice_api.post(f'/api/quotations/{quotation["id"]}/accept/').status_code, 404)
        self.assertEqual(self.staff_api.post(f'/api/quotations/{quotation["id"]}/accept/').status_code, 400)
        self.assertEqual(Quotation.objects.get(pk=quotation['id']).status, 'draft')

    def test_a_customer_cannot_accept_or_reject_someone_elses_quotation(self):
        quotation = self.sent_quotation()
        self.assertEqual(self.bob_api.post(f'/api/quotations/{quotation["id"]}/accept/').status_code, 404)
        self.assertEqual(self.bob_api.post(f'/api/quotations/{quotation["id"]}/reject/').status_code, 404)
        self.assertEqual(Quotation.objects.get(pk=quotation['id']).status, 'sent')

    def test_a_customer_can_reject_and_a_rejected_quotation_cannot_be_converted(self):
        quotation = self.sent_quotation()
        self.assertEqual(self.alice_api.post(f'/api/quotations/{quotation["id"]}/reject/').json()['status'], 'rejected')
        self.assertEqual(self.staff_api.post(f'/api/quotations/{quotation["id"]}/convert/').status_code, 400)
        self.assertEqual(self.alice_api.post(f'/api/quotations/{quotation["id"]}/accept/').status_code, 400)

    def test_an_expired_quotation_cannot_be_accepted_and_is_marked_expired(self):
        quotation = self.sent_quotation()
        Quotation.objects.filter(pk=quotation['id']).update(issued_date=TODAY - timedelta(days=30))
        response = self.alice_api.post(f'/api/quotations/{quotation["id"]}/accept/')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Quotation.objects.get(pk=quotation['id']).status, 'expired')
        self.assertEqual(self.staff_api.post(f'/api/quotations/{quotation["id"]}/convert/').status_code, 400)
        self.assertEqual(Subscription.objects.count(), 0)

    def test_the_last_day_of_validity_still_counts(self):
        quotation = self.sent_quotation()
        Quotation.objects.filter(pk=quotation['id']).update(issued_date=TODAY - timedelta(days=15))
        self.assertEqual(self.alice_api.post(f'/api/quotations/{quotation["id"]}/accept/').status_code, 200)

    def test_converting_twice_or_without_acceptance_is_refused(self):
        quotation = self.sent_quotation()
        self.assertEqual(self.staff_api.post(f'/api/quotations/{quotation["id"]}/convert/').status_code, 400)
        self.alice_api.post(f'/api/quotations/{quotation["id"]}/accept/')
        self.assertEqual(self.staff_api.post(f'/api/quotations/{quotation["id"]}/convert/').status_code, 200)
        self.assertEqual(self.staff_api.post(f'/api/quotations/{quotation["id"]}/convert/').status_code, 400)
        self.assertEqual(Subscription.objects.count(), 1)

    def test_a_quotation_without_a_plan_cannot_become_a_subscription(self):
        quotation = self.sent_quotation(plan=None)
        self.assertEqual(self.staff_api.post(f'/api/quotations/{quotation["id"]}/accept/').status_code, 200)
        response = self.staff_api.post(f'/api/quotations/{quotation["id"]}/convert/')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Subscription.objects.count(), 0)

    def test_customers_cannot_convert_or_edit(self):
        quotation = self.sent_quotation()
        self.alice_api.post(f'/api/quotations/{quotation["id"]}/accept/')
        self.assertEqual(self.alice_api.post(f'/api/quotations/{quotation["id"]}/convert/').status_code, 403)
        self.assertEqual(self.alice_api.patch(f'/api/quotations/{quotation["id"]}/', {'notes': 'x'}, format='json').status_code, 403)
        self.assertEqual(self.alice_api.delete(f'/api/quotations/{quotation["id"]}/').status_code, 403)

    def test_only_drafts_can_be_edited_or_deleted(self):
        draft = self.create_quotation().json()
        edited = self.staff_api.patch(
            f'/api/quotations/{draft["id"]}/', {'items': self.items(quantity=4)}, format='json'
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()['items'][0]['quantity'], 4)
        sent = self.sent_quotation()
        self.assertEqual(self.staff_api.patch(f'/api/quotations/{sent["id"]}/', {'notes': 'late edit'}, format='json').status_code, 400)
        self.assertEqual(self.staff_api.delete(f'/api/quotations/{sent["id"]}/').status_code, 400)
        self.assertEqual(self.staff_api.delete(f'/api/quotations/{draft["id"]}/').status_code, 204)

    def test_a_quotation_is_for_a_customer_account_and_needs_lines(self):
        self.assertEqual(self.create_quotation(customer=self.staff).status_code, 400)
        self.assertEqual(self.create_quotation(items=[]).status_code, 400)

    def test_quotation_lines_reject_nonsense_numbers(self):
        cases = {
            'negative price': self.items(price='-50.00'),
            'zero quantity': self.items(quantity=0),
            'tax above 100%': self.items(tax='150.00'),
        }
        for label, items in cases.items():
            with self.subTest(label):
                self.assertEqual(self.create_quotation(items=items).status_code, 400, f'{label} was accepted')

    def test_totals_add_up_across_several_lines_with_different_taxes(self):
        items = [
            {'product': self.product.id, 'quantity': 3, 'unit_price': '333.33', 'tax_rate': '18.00'},
            {'product': self.product.id, 'quantity': 1, 'unit_price': '100.00', 'tax_rate': '5.00'},
        ]
        body = self.create_quotation(items=items).json()
        self.assertEqual(body['subtotal'], '1099.99')
        self.assertEqual(body['tax_total'], '185.00')
        self.assertEqual(body['total'], '1284.99')


class PlanRequestTests(QuoteFlowCase):
    def active_subscriptions(self, user):
        return {
            s.plan.name: s.status
            for s in Subscription.objects.filter(customer=user).select_related('plan')
        }

    def test_a_customers_own_request_converts_the_moment_they_accept_it(self):
        requested = self.request_plan(self.alice_api, self.basic)
        self.assertEqual(requested.status_code, 201, requested.content)
        quotation = self.alice_api.get(f'/api/quotations/{requested.json()["quotation"]}/').json()
        self.assertEqual(quotation['status'], 'sent')
        self.assertEqual(quotation['created_by'], self.alice.id)
        item = quotation['items'][0]
        self.assertEqual((item['unit_price'], item['tax_rate'], item['quantity']), ('499.00', '18.00', 1))

        accepted = self.alice_api.post(f'/api/quotations/{quotation["id"]}/accept/')
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertIsNotNone(accepted.json()['subscription'])
        self.assertEqual(self.active_subscriptions(self.alice), {'Basic': 'active'})
        invoice = Invoice.objects.get(customer=self.alice)
        self.assertEqual(invoice.status, 'confirmed')
        self.assertEqual(invoice.amount, Decimal('588.82'))

    def test_an_upgrade_closes_the_old_plan_and_opens_the_new_one(self):
        first = self.request_plan(self.alice_api, self.basic).json()['quotation']
        self.alice_api.post(f'/api/quotations/{first}/accept/')
        relations = {p['name']: p['relation'] for p in self.alice_api.get('/api/catalog/plans/').json()}
        self.assertEqual(relations, {'Basic': 'current', 'Professional': 'upgrade', 'Enterprise': 'upgrade'})

        second = self.request_plan(self.alice_api, self.pro).json()['quotation']
        self.alice_api.post(f'/api/quotations/{second}/accept/')
        self.assertEqual(self.active_subscriptions(self.alice), {'Basic': 'closed', 'Professional': 'active'})
        old = Subscription.objects.get(customer=self.alice, plan=self.basic)
        self.assertEqual(old.end_date, TODAY)
        self.assertEqual(Subscription.objects.filter(customer=self.alice, status='active').count(), 1)

    def test_downgrades_the_current_plan_and_duplicates_are_refused(self):
        quotation = self.request_plan(self.alice_api, self.pro).json()['quotation']
        self.alice_api.post(f'/api/quotations/{quotation}/accept/')
        relations = {p['name']: p['relation'] for p in self.alice_api.get('/api/catalog/plans/').json()}
        self.assertEqual(relations['Basic'], 'downgrade')
        self.assertEqual(self.request_plan(self.alice_api, self.basic).status_code, 400)
        self.assertEqual(self.request_plan(self.alice_api, self.pro).status_code, 400)
        self.assertEqual(Quotation.objects.filter(customer=self.alice).count(), 1)

    def test_a_second_open_request_for_the_same_plan_is_refused_and_flagged(self):
        self.assertEqual(self.request_plan(self.bob_api, self.basic).status_code, 201)
        duplicate = self.request_plan(self.bob_api, self.basic)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(Quotation.objects.filter(customer=self.bob).count(), 1)
        flags = {p['name']: p['requested'] for p in self.bob_api.get('/api/catalog/plans/').json()}
        self.assertEqual(flags, {'Basic': True, 'Professional': False, 'Enterprise': False})

    def test_a_rejected_request_can_be_made_again(self):
        first = self.request_plan(self.bob_api, self.basic).json()['quotation']
        self.bob_api.post(f'/api/quotations/{first}/reject/')
        self.assertEqual(self.request_plan(self.bob_api, self.basic).status_code, 201)

    def test_only_customers_can_use_the_request_endpoint(self):
        self.assertEqual(self.request_plan(self.staff_api, self.basic).status_code, 403)
        self.assertEqual(self.request_plan(self.api(self.admin), self.basic).status_code, 403)
        self.assertEqual(self.request_plan(APIClient(), self.basic).status_code, 401)

    def test_customers_do_not_become_subscribed_twice_to_the_same_plan(self):
        quotation = self.request_plan(self.alice_api, self.basic).json()['quotation']
        self.alice_api.post(f'/api/quotations/{quotation}/accept/')
        staff_quote = self.sent_quotation(customer=self.alice, plan='basic')
        self.alice_api.post(f'/api/quotations/{staff_quote["id"]}/accept/')
        again = self.staff_api.post(f'/api/quotations/{staff_quote["id"]}/convert/')
        self.assertEqual(again.status_code, 400)
        self.assertEqual(Subscription.objects.filter(customer=self.alice, status='active').count(), 1)

    def test_request_prices_follow_the_plan_and_the_current_tax_rule(self):
        TaxRule.objects.filter(name='GST').update(rate=5)
        quotation = self.request_plan(self.bob_api, self.pro).json()['quotation']
        body = self.bob_api.get(f'/api/quotations/{quotation}/').json()
        self.assertEqual((body['subtotal'], body['tax_total'], body['total']), ('999.00', '49.95', '1048.95'))
        self.assertRegex(re.sub(r'\s', '', body['valid_until']), r'^\d{4}-\d{2}-\d{2}$')
