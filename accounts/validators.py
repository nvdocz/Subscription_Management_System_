import re

from django.core.exceptions import ValidationError


class BrightloopPasswordValidator:
    """More than eight characters, with an uppercase letter, a lowercase letter and a special character."""

    def validate(self, password, user=None):
        problems = []
        if len(password) <= 8:
            problems.append('be longer than 8 characters')
        if not re.search(r'[A-Z]', password):
            problems.append('include an uppercase letter')
        if not re.search(r'[a-z]', password):
            problems.append('include a lowercase letter')
        if not re.search(r'[^A-Za-z0-9]', password):
            problems.append('include a special character')
        if problems:
            raise ValidationError('Password must ' + ', '.join(problems) + '.', code='password_policy')

    def get_help_text(self):
        return 'More than 8 characters with an uppercase letter, a lowercase letter and a special character.'
