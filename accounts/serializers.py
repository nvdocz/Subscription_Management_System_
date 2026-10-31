from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .email_check import check_email
from .models import User
from .verification import NOT_VERIFIED_MESSAGE


def unique_email(value):
    email = value.strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise serializers.ValidationError('An account with this email already exists.')
    if settings.VERIFY_EMAIL_EXISTS:
        problem = check_email(email)
        if problem:
            raise serializers.ValidationError(problem)
    return email


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'role')
        extra_kwargs = {
            'role': {'default': User.Role.CUSTOMER},
        }

    def validate_email(self, value):
        return unique_email(value)

    def validate_role(self, value):
        if value != User.Role.CUSTOMER:
            raise serializers.ValidationError('Self-registration is only allowed for the customer role.')
        return value

    def create(self, validated_data):
        # Inactive until the owner opens the link mailed to the address, which proves it is a real inbox.
        return User.objects.create_user(is_active=False, **validated_data)


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except AuthenticationFailed:
            user = User.objects.filter(username=attrs.get(self.username_field), is_active=False).first()
            if user is not None and user.check_password(attrs.get('password', '')):
                raise AuthenticationFailed(NOT_VERIFIED_MESSAGE, code='email_not_verified') from None
            raise

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role
        return token


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'date_joined')
        read_only_fields = ('id', 'username', 'email', 'date_joined')


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'role')

    def validate_email(self, value):
        return unique_email(value)

    def validate_role(self, value):
        actor = self.context['request'].user
        if actor.role == User.Role.STAFF and value != User.Role.CUSTOMER:
            raise serializers.ValidationError('Staff can only create customer accounts.')
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserRoleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('role',)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
