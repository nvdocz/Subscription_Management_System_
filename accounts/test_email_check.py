from unittest import mock

from django.test import override_settings
from rest_framework.test import APITestCase

from accounts import email_check
from accounts.email_check import DomainDoesNotExist, NOT_FOUND_MESSAGE, check_email, mailbox_missing

PAYLOAD = {'username': 'newbie', 'email': 'newbie@gmail.com', 'password': 'Valid#Pass1'}


class EmailExistenceTests(APITestCase):
    def test_only_a_clear_no_such_user_answer_rejects_the_mailbox(self):
        gmail = b"5.1.1 The email account that you tried to reach does not exist. NoSuchUser"
        self.assertTrue(mailbox_missing(550, gmail))
        self.assertTrue(mailbox_missing(550, '5.1.1 User unknown'))
        self.assertFalse(mailbox_missing(250, 'OK'))
        self.assertFalse(mailbox_missing(550, '5.7.1 Blocked by policy'), 'a policy block is not proof the mailbox is fake')
        self.assertFalse(mailbox_missing(450, '4.2.0 try again later'))

    def test_a_domain_that_does_not_exist_is_refused(self):
        with mock.patch.object(email_check, 'mail_servers', side_effect=DomainDoesNotExist('nope.invalid')):
            self.assertEqual(check_email('x@nope.invalid'), NOT_FOUND_MESSAGE)

    def test_a_missing_mailbox_is_refused_and_a_real_one_passes(self):
        with mock.patch.object(email_check, 'mail_servers', return_value=['mx.example.net']):
            with mock.patch.object(email_check, 'probe_mailbox', return_value=False):
                self.assertEqual(check_email('ghost@gmail.com'), NOT_FOUND_MESSAGE)
            with mock.patch.object(email_check, 'probe_mailbox', return_value=True):
                self.assertIsNone(check_email('real@gmail.com'))

    def test_inconclusive_checks_let_real_people_through(self):
        with mock.patch.object(email_check, 'mail_servers', return_value=None):
            self.assertIsNone(check_email('anyone@somewhere.com'))

    def test_temporary_inboxes_are_refused(self):
        self.assertIn('Temporary', check_email('x@mailinator.com'))

    @override_settings(VERIFY_EMAIL_EXISTS=True)
    def test_registration_shows_email_does_not_exist(self):
        with mock.patch('accounts.serializers.check_email', return_value=NOT_FOUND_MESSAGE):
            response = self.client.post('/api/auth/register/', PAYLOAD, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['email'], [NOT_FOUND_MESSAGE])

    @override_settings(VERIFY_EMAIL_EXISTS=True)
    def test_registration_succeeds_for_an_address_that_exists(self):
        with mock.patch('accounts.serializers.check_email', return_value=None):
            response = self.client.post('/api/auth/register/', PAYLOAD, format='json')
        self.assertEqual(response.status_code, 201)

