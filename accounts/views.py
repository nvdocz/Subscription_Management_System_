from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .permissions import IsAdmin, IsAdminOrStaff
from .verification import send_verification_email, user_for_link
from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserCreateSerializer,
    UserRoleUpdateSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        send_verification_email(user)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user = user_for_link(request.data.get('uid', ''), request.data.get('token', ''))
        if user is None:
            return Response({'detail': 'This confirmation link is invalid or has expired.'}, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
        return Response({'detail': 'Email confirmed. You can log in now.'})


class ResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data['email'], is_active=False).first()
        if user is not None:
            send_verification_email(user)
        return Response({'detail': 'If that account is waiting for confirmation, a new link has been sent.'})


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserListView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrStaff]

    def get_queryset(self):
        users = User.objects.order_by('username')
        if self.request.user.role == User.Role.STAFF:
            users = users.filter(role=User.Role.CUSTOMER)
        return users

    def get_serializer_class(self):
        return UserCreateSerializer if self.request.method == 'POST' else UserSerializer


class UserRoleUpdateView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRoleUpdateSerializer
    permission_classes = [IsAdmin]

    def perform_update(self, serializer):
        if serializer.instance.pk == self.request.user.pk:
            raise ValidationError('You cannot change your own role.')
        serializer.save()


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_link = f'{settings.FRONTEND_URL}/reset-password/{uid}/{token}/'
            send_mail(
                subject='Reset your password',
                message=f'Use the link below to reset your password:\n\n{reset_link}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )

        return Response(
            {'detail': 'If an account with that email exists, a reset link has been sent.'},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None

        if user is None or not default_token_generator.check_token(user, token):
            return Response({'detail': 'Invalid or expired reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Password has been reset successfully.'}, status=status.HTTP_200_OK)
