"""Email verification for new sign-ups: an account stays inactive until its owner opens the link mailed to them."""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User

NOT_VERIFIED_MESSAGE = 'Please verify your email first. We sent a confirmation link to your inbox.'


def send_verification_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f'{settings.FRONTEND_URL}/verify-email/{uid}/{token}/'
    send_mail(
        subject='Confirm your email address',
        message=(
            f'Hi {user.username},\n\nConfirm your email to activate your Brightloop account:\n\n{link}\n\n'
            'If you did not create this account you can ignore this message.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def user_for_link(uid, token):
    """The user a verification link belongs to, or None when the link is wrong or expired."""
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None
    return user if default_token_generator.check_token(user, token) else None
