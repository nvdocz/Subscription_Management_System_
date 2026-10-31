"""PDF story: a new customer signs up, forgets the password, and only the admin can add staff."""

import re

from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User

FAST = dict(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='http://frontend.test',
)

RULES = {
    'longer than 8': 'Short1!',
    'uppercase': 'alllowercase1!',
    'lowercase': 'ALLUPPERCASE1!',
    'special': 'NoSpecial1234',
}


@override_settings(**FAST)
class SignUpTests(APITestCase):
    def register(self, **overrides):
        payload = {'username': 'newbie', 'email': 'newbie@example.com', 'password': 'Valid#Pass1'}
        payload.update(overrides)
        return self.client.post('/api/auth/register/', payload, format='json')

    def test_a_customer_can_sign_up_with_a_valid_password(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['role'], 'customer')
        user = User.objects.get(username='newbie')
        self.assertTrue(user.check_password('Valid#Pass1'))
        self.assertNotEqual(user.password, 'Valid#Pass1')

    def test_nine_characters_is_enough_but_eight_is_not(self):
        self.assertEqual(self.register(password='Abcdef1!').status_code, 400)
        self.assertEqual(self.register(username='nine', email='nine@example.com', password='Abcdefg1!').status_code, 201)

    def test_self_registration_can_never_create_staff_or_admin(self):
        for role in ('staff', 'admin'):
            response = self.register(username=f'x{role}', email=f'{role}@example.com', role=role)
            self.assertEqual(response.status_code, 400, role)
        self.assertFalse(User.objects.filter(role__in=['staff', 'admin']).exists())

    def test_each_password_rule_fails_on_its_own_with_a_readable_message(self):
        for fragment, password in RULES.items():
            with self.subTest(rule=fragment):
                response = self.register(password=password)
                self.assertEqual(response.status_code, 400)
                message = ' '.join(response.json()['password'])
                self.assertIn(fragment, message)
                for other in RULES:
                    if other != fragment:
                        self.assertNotIn(other, message, f'{password!r} wrongly mentions the "{other}" rule')

    def test_a_password_that_breaks_every_rule_lists_every_problem(self):
        message = ' '.join(self.register(password='1234').json()['password'])
        for fragment in RULES:
            self.assertIn(fragment, message)

    def test_each_email_belongs_to_one_account_whatever_its_case(self):
        self.assertEqual(self.register().status_code, 201)
        for email in ('newbie@example.com', 'NEWBIE@Example.com'):
            response = self.register(username=f'other{len(email)}', email=email)
            self.assertEqual(response.status_code, 400, email)
            self.assertIn('email', response.json())
        self.assertEqual(User.objects.filter(email__iexact='newbie@example.com').count(), 1)

    def test_emails_are_stored_in_lower_case(self):
        self.register(username='mixed', email='Mixed.Case@Example.com')
        self.assertEqual(User.objects.get(username='mixed').email, 'mixed.case@example.com')

    def test_usernames_are_unique_too(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register(email='second@example.com').status_code, 400)

    def test_login_returns_tokens_that_carry_the_role(self):
        self.register()
        User.objects.filter(username='newbie').update(is_active=True)  # as if the emailed link was opened
        response = self.client.post('/api/auth/login/', {'username': 'newbie', 'password': 'Valid#Pass1'}, format='json')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['access'] and body['refresh'])
        token = AccessToken(body['access'])
        self.assertEqual(token['role'], 'customer')
        self.assertEqual(token['username'], 'newbie')
        me = APIClient()
        me.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
        self.assertEqual(me.get('/api/auth/me/').json()['email'], 'newbie@example.com')

    def test_login_refuses_a_wrong_password(self):
        self.register()
        response = self.client.post('/api/auth/login/', {'username': 'newbie', 'password': 'Wrong#Pass1'}, format='json')
        self.assertEqual(response.status_code, 401)


@override_settings(**FAST)
class PasswordResetTests(APITestCase):
    OLD, NEW = 'Old#Passw0rd', 'Brand#New1pass'

    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', self.OLD, role='customer')

    def request_reset(self, email='alice@example.com'):
        return self.client.post('/api/auth/password-reset/', {'email': email}, format='json')

    def link_parts(self):
        body = mail.outbox[0].body
        match = re.search(r'/reset-password/([^/\s]+)/([^/\s]+)/', body)
        self.assertIsNotNone(match, body)
        return match.group(1), match.group(2)

    def confirm(self, uid, token, password):
        return self.client.post(
            '/api/auth/password-reset/confirm/', {'uid': uid, 'token': token, 'new_password': password}, format='json'
        )

    def login(self, password):
        return self.client.post('/api/auth/login/', {'username': 'alice', 'password': password}, format='json')

    def test_a_registered_email_gets_exactly_one_email_with_a_reset_link(self):
        response = self.request_reset()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['alice@example.com'])
        self.assertIn('http://frontend.test/reset-password/', message.body)
        self.link_parts()

    def test_the_email_is_found_whatever_its_case(self):
        self.request_reset('ALICE@Example.com')
        self.assertEqual(len(mail.outbox), 1)

    def test_an_unknown_email_gets_the_same_answer_and_no_email(self):
        known = self.request_reset()
        mail.outbox.clear()
        unknown = self.request_reset('nobody@example.com')
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(unknown.json(), known.json())
        self.assertEqual(len(mail.outbox), 0)

    def test_a_malformed_email_is_rejected(self):
        self.assertEqual(self.request_reset('not-an-email').status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_a_weak_new_password_is_refused_and_does_not_burn_the_link(self):
        self.request_reset()
        uid, token = self.link_parts()
        weak = self.confirm(uid, token, 'weakpass')
        self.assertEqual(weak.status_code, 400)
        self.assertIn('new_password', weak.json())
        self.assertEqual(self.confirm(uid, token, self.NEW).status_code, 200)

    def test_a_strong_password_resets_it_and_only_the_new_one_logs_in(self):
        self.request_reset()
        uid, token = self.link_parts()
        self.assertEqual(self.confirm(uid, token, self.NEW).status_code, 200)
        self.assertEqual(self.login(self.NEW).status_code, 200)
        self.assertEqual(self.login(self.OLD).status_code, 401)

    def test_a_reset_link_works_once(self):
        self.request_reset()
        uid, token = self.link_parts()
        self.assertEqual(self.confirm(uid, token, self.NEW).status_code, 200)
        again = self.confirm(uid, token, 'Another#Pass22')
        self.assertEqual(again.status_code, 400)
        self.assertEqual(self.login(self.NEW).status_code, 200)

    def test_garbage_links_are_refused(self):
        self.request_reset()
        uid, token = self.link_parts()
        self.assertEqual(self.confirm(uid, 'bogus-token', self.NEW).status_code, 400)
        self.assertEqual(self.confirm('not-a-uid', token, self.NEW).status_code, 400)
        self.assertEqual(self.confirm(uid, token[:-2] + 'zz', self.NEW).status_code, 400)
        self.assertEqual(self.login(self.OLD).status_code, 200)


@override_settings(**FAST)
class StaffAccountTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('boss', 'boss@example.com', 'Boss#Pass123', role='admin')
        self.staff = User.objects.create_user('rep', 'rep@example.com', 'Rep#Pass1234', role='staff')
        self.customer = User.objects.create_user('alice', 'alice@example.com', 'Alice#Pass12', role='customer')

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def payload(self, role, name='newstaff'):
        return {'username': name, 'email': f'{name}@example.com', 'password': 'Staff#Pass12', 'role': role}

    def test_only_the_admin_can_add_staff(self):
        refused = self.as_user(self.staff).post('/api/auth/users/', self.payload('staff'), format='json')
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(self.as_user(self.customer).post('/api/auth/users/', self.payload('staff'), format='json').status_code, 403)
        self.assertEqual(APIClient().post('/api/auth/users/', self.payload('staff'), format='json').status_code, 401)
        self.assertFalse(User.objects.filter(username='newstaff').exists())
        created = self.as_user(self.admin).post('/api/auth/users/', self.payload('staff'), format='json')
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()['role'], 'staff')

    def test_a_new_staff_member_can_log_in_and_is_staff(self):
        self.as_user(self.admin).post('/api/auth/users/', self.payload('staff'), format='json')
        login = APIClient().post('/api/auth/login/', {'username': 'newstaff', 'password': 'Staff#Pass12'}, format='json')
        self.assertEqual(login.status_code, 200)
        self.assertEqual(AccessToken(login.json()['access'])['role'], 'staff')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        self.assertEqual(client.get('/api/auth/me/').json()['role'], 'staff')

    def test_staff_can_add_customers_but_not_other_staff_or_admins(self):
        client = self.as_user(self.staff)
        self.assertEqual(client.post('/api/auth/users/', self.payload('customer', 'newcust'), format='json').status_code, 201)
        for role in ('staff', 'admin'):
            self.assertEqual(client.post('/api/auth/users/', self.payload(role, f'try{role}'), format='json').status_code, 400)

    def test_staff_only_ever_see_customer_accounts(self):
        rows = self.as_user(self.staff).get('/api/auth/users/').json()
        self.assertEqual({row['role'] for row in rows}, {'customer'})
        everyone = self.as_user(self.admin).get('/api/auth/users/').json()
        self.assertEqual({row['role'] for row in everyone}, {'admin', 'staff', 'customer'})

    def test_account_creation_applies_the_same_password_and_email_rules(self):
        client = self.as_user(self.admin)
        self.assertEqual(client.post('/api/auth/users/', {**self.payload('staff'), 'password': 'weak'}, format='json').status_code, 400)
        duplicate = client.post('/api/auth/users/', {**self.payload('staff'), 'email': 'ALICE@example.com'}, format='json')
        self.assertEqual(duplicate.status_code, 400)
