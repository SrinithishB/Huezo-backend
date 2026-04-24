from rest_framework import serializers
from django.utils import timezone
from .models import User, Customer, UserRole


# AUTH SERIALIZERS

class RegisterSerializer(serializers.ModelSerializer):
    """
    Register a new customer — creates both User + Customer profile.
    """
    password         = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    # Customer profile fields (flat)
    brand_name      = serializers.CharField(max_length=200)
    contact_name    = serializers.CharField(max_length=150)
    phone           = serializers.CharField(max_length=20)
    alternate_phone = serializers.CharField(max_length=20,  required=False, allow_blank=True)
    address_line1   = serializers.CharField(required=False, allow_blank=True)
    address_line2   = serializers.CharField(required=False, allow_blank=True)
    city            = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state           = serializers.CharField(max_length=100, required=False, allow_blank=True)
    pin_code        = serializers.CharField(max_length=12,  required=False, allow_blank=True)
    country         = serializers.CharField(max_length=80,  required=False, default="India")

    class Meta:
        model  = User
        fields = [
            "email", "password", "confirm_password",
            "brand_name", "contact_name", "phone", "alternate_phone",
            "address_line1", "address_line2", "city", "state", "pin_code", "country",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("confirm_password"):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        profile_fields = [
            "brand_name", "contact_name", "phone", "alternate_phone",
            "address_line1", "address_line2", "city", "state", "pin_code", "country",
        ]
        profile_data = {f: validated_data.pop(f) for f in profile_fields if f in validated_data}
        user = User.objects.create_user(**validated_data)
        Customer.objects.create(user=user, **profile_data)
        return user


class LoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            user = User.objects.get(email=attrs["email"])
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials.")

        if not user.is_active:
            raise serializers.ValidationError("This account has been disabled.")

        if user.is_locked:
            raise serializers.ValidationError(
                f"Account locked until {user.locked_until.strftime('%Y-%m-%d %H:%M')} UTC."
            )

        if not user.check_password(attrs["password"]):
            user.record_failed_login()
            if not user.is_locked:
                raise serializers.ValidationError("Invalid credentials.")
            raise serializers.ValidationError("Account locked due to too many failed attempts.")

        user.record_successful_login()
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password     = serializers.CharField(write_only=True)
    new_password     = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


# USER SERIALIZER

class UserDetailSerializer(serializers.ModelSerializer):
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model  = User
        fields = [
            "id", "email", "role", "is_active", "is_locked",
            "last_login_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "role", "is_active", "is_locked",
            "last_login_at", "created_at", "updated_at",
        ]


# CUSTOMER SERIALIZERS

class CustomerDetailSerializer(serializers.ModelSerializer):
    email             = serializers.EmailField(source="user.email", read_only=True)
    is_active         = serializers.BooleanField(source="user.is_active", read_only=True)
    last_login_at     = serializers.DateTimeField(source="user.last_login_at", read_only=True)
    full_address      = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model  = Customer
        fields = [
            "id", "email", "is_active",
            "brand_name", "contact_name", "phone", "alternate_phone",
            "address_line1", "address_line2", "city", "state", "pin_code", "country",
            "full_address", "profile_picture_url",
            "last_login_at", "created_at", "updated_at",
        ]

    def get_full_address(self, obj):
        return obj.full_address()

    def get_profile_picture_url(self, obj):
        request = self.context.get("request")
        if obj.profile_picture and request:
            return request.build_absolute_uri(obj.profile_picture.url)
        return None


class CustomerUpdateSerializer(serializers.ModelSerializer):
    """Customer updates their own profile."""
    class Meta:
        model  = Customer
        fields = [
            "brand_name", "contact_name", "phone", "alternate_phone",
            "address_line1", "address_line2", "city", "state", "pin_code", "country",
            "profile_picture",
        ]
        extra_kwargs = {f: {"required": False} for f in fields}


class CustomerPickerSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for staff to search and select a customer
    when placing an order on their behalf.
    """
    user_id   = serializers.UUIDField(source="user.id",       read_only=True)
    email     = serializers.EmailField(source="user.email",   read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)

    class Meta:
        model  = Customer
        fields = [
            "user_id", "email",
            "brand_name", "contact_name", "phone",
            "city", "state", "is_active",
        ]