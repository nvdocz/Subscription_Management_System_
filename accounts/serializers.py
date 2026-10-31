from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


def unique_email(value):
    email = value.strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise serializers.ValidationError('An account with this email already exists.')
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
        return User.objects.create_user(**validated_data)


class LoginSerializer(TokenObtainPairSerializer):
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
