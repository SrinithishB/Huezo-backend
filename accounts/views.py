from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import NotFound
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import User, Customer
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    UserDetailSerializer,
    CustomerDetailSerializer,
    CustomerUpdateSerializer,
)


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