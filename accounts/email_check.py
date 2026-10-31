"""Checks that an email address can really receive mail, so fake addresses are refused at sign-up.

1. the domain must exist and accept mail (DNS MX lookup),
2. the mail server is asked whether the mailbox exists (SMTP RCPT TO, nothing is sent),
3. throwaway-inbox domains are refused.

Anything inconclusive (no internet, server blocks probing, timeouts) is allowed through, so a real person is never
locked out by a flaky check. Only clear "does not exist" answers reject the address.
"""

import re
import smtplib

import dns.exception
import dns.resolver

NOT_FOUND_MESSAGE = 'This email address does not exist. Please enter a real email address.'
DISPOSABLE_MESSAGE = 'Temporary email addresses are not allowed. Please use your real email address.'
PROBE_SENDER = 'verify@brightloop.example'
DNS_TIMEOUT = 4
SMTP_TIMEOUT = 6

DISPOSABLE_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'guerrillamail.net', '10minutemail.com', 'tempmail.com', 'temp-mail.org',
    'throwawaymail.com', 'yopmail.com', 'trashmail.com', 'getnada.com', 'sharklasers.com', 'dispostable.com',
    'maildrop.cc', 'fakeinbox.com', 'mohmal.com', 'tempmailo.com', 'emailondeck.com', 'mintemail.com',
}

# 5.1.1 bad mailbox, 5.1.2 bad domain, 5.1.3 bad address, 5.1.6 mailbox moved. Plain-text fallbacks for old servers.
NO_SUCH_MAILBOX = re.compile(
    r'(5\.1\.[1236])|(no such (user|mailbox|recipient))|(user (unknown|not found|doesn.t exist))'
    r'|(does not exist)|(unknown (user|recipient))|(invalid (recipient|mailbox))|(mailbox (unavailable|not found))',
    re.IGNORECASE,
)


class DomainDoesNotExist(Exception):
    pass


def mail_servers(domain):
    """Hosts that accept mail for ``domain``, best first. Returns None when DNS could not give a clear answer."""
    try:
        answers = dns.resolver.resolve(domain, 'MX', lifetime=DNS_TIMEOUT)
        hosts = [str(r.exchange).rstrip('.') for r in sorted(answers, key=lambda r: r.preference)]
        hosts = [h for h in hosts if h]
        if not hosts:  # a lone "." is a null MX: the domain says it accepts no mail
            raise DomainDoesNotExist(domain)
        return hosts
    except dns.resolver.NXDOMAIN:
        raise DomainDoesNotExist(domain) from None
    except dns.resolver.NoAnswer:
        try:
            dns.resolver.resolve(domain, 'A', lifetime=DNS_TIMEOUT)
            return [domain]
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            raise DomainDoesNotExist(domain) from None
        except dns.exception.DNSException:
            return None
    except dns.exception.DNSException:
        return None


def mailbox_missing(code, message):
    """True only when the server clearly says this mailbox does not exist."""
    text = message.decode(errors='ignore') if isinstance(message, bytes) else str(message)
    return code in (550, 551, 553) and bool(NO_SUCH_MAILBOX.search(text))


def probe_mailbox(host, email):
    """Ask the mail server if the mailbox exists. Returns False only for a clear 'no such user'."""
    try:
        with smtplib.SMTP(timeout=SMTP_TIMEOUT) as server:
            server.connect(host, 25)
            server.ehlo('brightloop.example')
            server.mail(PROBE_SENDER)
            code, message = server.rcpt(email)
    except (OSError, smtplib.SMTPException):
        return True
    return not mailbox_missing(code, message)


def check_email(email):
    """Return an error message if the address is fake, otherwise None."""
    domain = email.rsplit('@', 1)[-1].lower()
    if domain in DISPOSABLE_DOMAINS:
        return DISPOSABLE_MESSAGE
    try:
        hosts = mail_servers(domain)
    except DomainDoesNotExist:
        return NOT_FOUND_MESSAGE
    if hosts and not probe_mailbox(hosts[0], email):
        return NOT_FOUND_MESSAGE
    return None
