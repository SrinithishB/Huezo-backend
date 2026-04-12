import secrets
import random
import logging
from datetime import timedelta

from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import NotFound
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from django.utils import timezone

logger = logging.getLogger(__name__)

from .models import User, Customer, PasswordResetOTP
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    UserDetailSerializer,
    CustomerDetailSerializer,
    CustomerUpdateSerializer,
    CustomerPickerSerializer,
)
from .permissions import IsAdminOrStaff


# ======================================================================
# HELPERS
# ======================================================================

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access":  str(refresh.access_token),
    }


# ======================================================================
# AUTH VIEWS
# ======================================================================

class RegisterView(APIView):
    """
    POST /api/auth/register/
    Public — creates a customer user + profile in one request.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user   = serializer.save()
        tokens = get_tokens_for_user(user)
        return Response(
            {
                "message": "Registration successful.",
                "user": {"id": str(user.id), "email": user.email, "role": user.role},
                **tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    POST /api/auth/login/
    Public — validates credentials, handles lockout, returns JWT tokens.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user   = serializer.validated_data["user"]
        tokens = get_tokens_for_user(user)
        return Response(
            {
                "message": "Login successful.",
                "user": {"id": str(user.id), "email": user.email, "role": user.role},
                **tokens,
            }
        )


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blacklists the refresh token — invalidates the session.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data["refresh"])
            token.blacklist()
            return Response({"message": "Logged out successfully."})
        except Exception:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TokenRefreshView(TokenRefreshView):
    """
    POST /api/auth/token/refresh/
    Exchange a valid refresh token for a new access token.
    """
    pass


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/
    Authenticated user changes their own password.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])
        return Response({"message": "Password changed successfully."})


class MeView(APIView):
    """
    GET   /api/auth/me/   — return current user's account info
    PATCH /api/auth/me/   — update email
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserDetailSerializer(request.user).data)

    def patch(self, request):
        serializer = UserDetailSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ======================================================================
# CUSTOMER PROFILE VIEWS  (self-service)
# ======================================================================

class MyCustomerProfileView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/customers/me/   — view own customer profile
    PATCH /api/customers/me/   — update own customer profile (multipart for profile_picture)
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]
    http_method_names  = ["get", "patch"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return CustomerUpdateSerializer
        return CustomerDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_object(self):
        try:
            return Customer.objects.select_related(
                "user", "created_by_admin"
            ).get(user=self.request.user)
        except Customer.DoesNotExist:
            raise NotFound("Customer profile not found for this account.")


# ======================================================================
# FORGOT PASSWORD — OTP FLOW
# ======================================================================

class OTPRateThrottle(AnonRateThrottle):
    rate = "5/hour"
    scope = "otp"


class LoginRateThrottle(AnonRateThrottle):
    rate = "10/hour"
    scope = "login"


class ForgotPasswordRequestView(APIView):
    """
    POST /api/auth/forgot-password/
    Public — send a 6-digit OTP to the user's registered email.
    Rate limited to 5 requests/hour per IP.
    """
    permission_classes = [AllowAny]
    throttle_classes   = [OTPRateThrottle]

    def post(self, request):
        from django.conf import settings as django_settings

        email = request.data.get("email", "").strip().lower()
        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Always return the same message to prevent email enumeration
        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response({"message": "If this email is registered, an OTP has been sent."})

        # Use secrets for cryptographically secure OTP
        otp        = f"{secrets.randbelow(1000000):06d}"
        expires_at = timezone.now() + timedelta(
            minutes=getattr(django_settings, "OTP_EXPIRY_MINUTES", 10)
        )

        # Atomic update-or-create prevents race condition
        PasswordResetOTP.objects.update_or_create(
            user       = user,
            is_verified = False,
            defaults   = {"otp": otp, "expires_at": expires_at, "reset_token": ""},
        )

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            expiry  = getattr(django_settings, "OTP_EXPIRY_MINUTES", 10)
            message = Mail(
                from_email    = django_settings.DEFAULT_FROM_EMAIL,
                to_emails     = user.email,
                subject       = "Your Huezo Password Reset OTP",
                plain_text_content = (
                    f"Hi {user.email},\n\n"
                    f"Your OTP for password reset is: {otp}\n\n"
                    f"This OTP is valid for {expiry} minutes.\n\n"
                    f"If you did not request this, please ignore this email.\n\n"
                    f"— Huezo Team"
                ),
            )
            SendGridAPIClient(django_settings.SENDGRID_API_KEY).send(message)
        except Exception as e:
            logger.error(f"OTP email failed for {email}: {e}")
            return Response(
                {"error": "Failed to send OTP. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"message": "If this email is registered, an OTP has been sent."})


class ForgotPasswordVerifyOTPView(APIView):
    """
    POST /api/auth/forgot-password/verify-otp/
    Public — verify OTP and receive a short-lived reset token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        otp   = request.data.get("otp", "").strip()

        if not email or not otp:
            return Response(
                {"error": "Email and OTP are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid OTP or email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        record = PasswordResetOTP.objects.filter(
            user=user, otp=otp, is_verified=False
        ).order_by("-created_at").first()

        if not record:
            return Response(
                {"error": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if record.is_expired():
            return Response(
                {"error": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate a secure reset token
        import secrets
        reset_token = secrets.token_hex(32)
        record.is_verified  = True
        record.reset_token  = reset_token
        record.save(update_fields=["is_verified", "reset_token"])

        return Response({
            "message": "OTP verified successfully.",
            "reset_token": reset_token,
        })


class ForgotPasswordResetView(APIView):
    """
    POST /api/auth/forgot-password/reset/
    Public — set a new password using the reset token from verify step.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        reset_token      = request.data.get("reset_token", "").strip()
        new_password     = request.data.get("new_password", "").strip()
        confirm_password = request.data.get("confirm_password", "").strip()

        if not reset_token or not new_password or not confirm_password:
            return Response(
                {"error": "reset_token, new_password and confirm_password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {"error": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {"error": "Password must be at least 8 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone
        record = PasswordResetOTP.objects.filter(
            reset_token=reset_token, is_verified=True
        ).select_related("user").first()

        if not record:
            return Response(
                {"error": "Invalid or expired reset token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if record.is_expired():
            return Response(
                {"error": "Reset token has expired. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set the new password
        user = record.user
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])

        # Clean up all OTP records for this user
        PasswordResetOTP.objects.filter(user=user).delete()

        return Response({"message": "Password reset successfully. Please log in."})


# ======================================================================
# STAFF: CUSTOMER PICKER
# ======================================================================

class CustomerListView(generics.ListAPIView):
    """
    GET /api/customers/
    Staff / Admin — search and list all customers to pick when placing an order.

    Query params:
      ?search=   searches brand_name, contact_name, email, phone
      ?city=     filter by city (partial match)
      ?state=    filter by state (partial match)
      ?page=     page number (20 per page)
    """
    serializer_class   = CustomerPickerSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = [
        "brand_name", "contact_name", "phone",
        "user__email",
    ]
    ordering_fields    = ["brand_name", "created_at"]
    ordering           = ["brand_name"]

    def get_queryset(self):
        qs = Customer.objects.select_related("user").filter(user__is_active=True)
        city  = self.request.query_params.get("city")
        state = self.request.query_params.get("state")
        if city:
            qs = qs.filter(city__icontains=city)
        if state:
            qs = qs.filter(state__icontains=state)
        return qs


class CustomerDetailAdminView(APIView):
    """
    GET /api/customers/<user_id>/
    Staff / Admin — fetch full profile of a specific customer by their user UUID.
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request, user_id):
        try:
            customer = Customer.objects.select_related(
                "user", "created_by_admin"
            ).get(user__id=user_id)
        except Customer.DoesNotExist:
            return Response({"error": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = CustomerDetailSerializer(customer, context={"request": request})
        return Response(serializer.data)