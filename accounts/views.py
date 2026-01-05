from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.models import User
from rest_framework.views import APIView
from django.core.mail import send_mail
from .models import EmailOTP
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import (
    UserSerializer,
    RequestOTPSerializer,
    VerifyOTPSerializer,
    EmailOrUsernameTokenObtainPairSerializer,
)
from rest_framework.response import Response
from .utils import create_otp_record, hash_otp
from django.conf import settings
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
import secrets


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = getattr(request, "user", None)
        name = (f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}").strip()
        if not name:
            name = (getattr(user, "username", "") or "").strip()
        if not name:
            name = (getattr(user, "email", "") or "").strip()
        return Response(
            {
                "user": UserSerializer(user).data,
                "is_hotel_account": bool(user and hasattr(user, "hotel_account")),
                "email": getattr(user, "email", None),
                "name": name,
                "role": "partner" if (user and hasattr(user, "hotel_account")) else "user",
            },
            status=200,
        )


class GoogleLoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        token = request.data.get("id_token")
        if not token:
            return Response({"detail": "id_token required."}, status=400)

        client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
        if not client_id:
            return Response({"detail": "Google login not configured on server."}, status=500)

        try:
            idinfo = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                client_id,
            )
        except Exception:
            return Response({"detail": "Invalid Google token."}, status=400)

        email = idinfo.get("email")
        email_verified = idinfo.get("email_verified")
        if not email or not email_verified:
            return Response({"detail": "Unverified Google email."}, status=400)

        base_username = email.split("@")[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": username, "is_active": True},
        )

        if not user.is_active:
            user.is_active = True
            user.save()

        refresh = RefreshToken.for_user(user)
        user_serializer = UserSerializer(user)
        name = (f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}").strip()
        if not name:
            name = (getattr(user, "username", "") or "").strip()
        if not name:
            name = (getattr(user, "email", "") or "").strip()
        return Response(
            {
                "user": user_serializer.data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "email": getattr(user, "email", None),
                "name": name,
                "role": "partner" if hasattr(user, "hotel_account") else "user",
            },
            status=200,
        )


class EmailOrUsernameTokenObtainPairView(TokenObtainPairView):
    """JWT login view that accepts either username or email.

    The frontend should POST {"username": "<email or username>", "password": "..."}
    to /api/auth/token/. This view uses EmailOrUsernameTokenObtainPairSerializer
    to resolve an email into the correct Django username before issuing tokens.
    """

    serializer_class = EmailOrUsernameTokenObtainPairSerializer



class RequestRegisterView(APIView):
    """
    Creates inactive user and sends OTP to email.
    """
    permission_classes = (AllowAny,)
    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email=email).first()
        if not user:
            base_username = email.split("@")[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            user = User.objects.create_user(username=username, email=email, password=None, is_active=False)

        otp, _ = create_otp_record(email, expiry_minutes=2)

        # send email (in prod use Celery)
        try:
            send_mail(
                subject="Your 1500rs registration OTP",
                message=f"Your OTP code is: {otp}\nIt expires in 2 minutes.",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            # cleanup user if email failed
            user.delete()
            return Response({"detail":f"Failed to send email: {str(e)}"}, status=500)

        return Response({"detail":"OTP sent to email. Verify to activate account."}, status=200)


class VerifyRegisterOTPView(APIView):
    """
    Verify OTP for registration. Activates user and returns tokens.
    """
    permission_classes = (AllowAny,)
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        record = EmailOTP.objects.filter(email=email).order_by("-created_at").first()
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"detail":"Invalid email or OTP."}, status=400)

        if not record or record.used or record.is_expired() or record.attempts >= 5:
            return Response({"detail":"Invalid or expired OTP."}, status=400)

        # verify hashed OTP
        candidate_hash = hash_otp(otp, record.salt)
        if secrets.compare_digest(candidate_hash, record.otp_hash):
            # success: mark used, activate user, return tokens
            record.used = True
            record.save()
            user.is_active = True
            user.save()

            refresh = RefreshToken.for_user(user)
            name = (f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}").strip()
            if not name:
                name = (getattr(user, "username", "") or "").strip()
            if not name:
                name = (getattr(user, "email", "") or "").strip()
            return Response({
                "detail":"OTP verified. Account activated.",
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "email": getattr(user, "email", None),
                "name": name,
                "role": "partner" if hasattr(user, "hotel_account") else "user",
            }, status=200)
        else:
            record.attempts += 1
            record.save()
            return Response({"detail":"Invalid OTP."}, status=400)
