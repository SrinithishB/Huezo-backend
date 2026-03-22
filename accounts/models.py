import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserRole(models.TextChoices):
    ADMIN    = "admin",    "Admin"     # Full access + Django admin panel (except user creation)
    STAFF    = "staff",    "Staff"     # Admin panel access — view only
    CUSTOMER = "customer", "Customer"  # End users — NO admin panel access


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        extra_fields.setdefault("role", UserRole.CUSTOMER)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_staff_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", UserRole.STAFF)
        return self.create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["is_staff"]     = True
        extra_fields["is_superuser"] = True
        extra_fields.setdefault("role", UserRole.ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
                          help_text="Auto-generated primary key.")
    email = models.EmailField(max_length=255, unique=True,
                              help_text="Login email address.")
    role = models.CharField(
        max_length=10, choices=UserRole.choices, default=UserRole.CUSTOMER,
        help_text="'admin' | 'staff' | 'customer' — drives all access control.",
    )
    is_active = models.BooleanField(default=True,
                                    help_text="Soft-disable without deleting the record.")
    is_staff  = models.BooleanField(default=False,
                                    help_text="True for admin + staff; controls Django admin panel access.")
    failed_login_attempts = models.SmallIntegerField(default=0)
    locked_until          = models.DateTimeField(null=True, blank=True)
    last_login_at         = models.DateTimeField(null=True, blank=True)
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()
    MAX_FAILED_ATTEMPTS = 5

    class Meta:
        db_table            = "users"
        verbose_name        = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.email} ({self.role})"

    # ── SAVE — sync is_staff with role ────────────────────────────────
    def save(self, *args, **kwargs):
        if not self.is_superuser:
            # admin + staff → can log in to Django admin panel
            self.is_staff = self.role in (UserRole.ADMIN, UserRole.STAFF)
        super().save(*args, **kwargs)

    # ── DJANGO ADMIN PERMISSION OVERRIDES ─────────────────────────────

    def has_perm(self, perm, obj=None):
        if not self.is_active or self.is_locked:
            return False
        if self.is_superuser:
            return True
        if self.role == UserRole.ADMIN:
            # Admin can do everything EXCEPT create or delete users
            blocked_perms = {
                "accounts.add_user",
                "accounts.delete_user",
            }
            if perm in blocked_perms:
                return False
            return True
        if self.role == UserRole.STAFF:
            # Staff: view only
            action = perm.split(".")[-1] if "." in perm else ""
            return action.startswith("view_")
        return False

    def has_module_perms(self, app_label):
        if not self.is_active or self.is_locked:
            return False
        if self.is_superuser:
            return True
        if self.role in (UserRole.ADMIN, UserRole.STAFF):
            return True
        return False

    # ── ROLE HELPERS ──────────────────────────────────────────────────

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_staff_member(self) -> bool:
        return self.role == UserRole.STAFF

    @property
    def is_customer(self) -> bool:
        return self.role == UserRole.CUSTOMER

    # ── LOCKOUT HELPERS ───────────────────────────────────────────────

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def record_failed_login(self, lock_duration_minutes: int = 30) -> None:
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            self.locked_until = timezone.now() + timezone.timedelta(
                minutes=lock_duration_minutes
            )
        self.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])

    def record_successful_login(self) -> None:
        self.failed_login_attempts = 0
        self.locked_until          = None
        self.last_login_at         = timezone.now()
        self.save(update_fields=[
            "failed_login_attempts", "locked_until",
            "last_login_at", "updated_at",
        ])


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
                          help_text="1-to-1 with users table.")
    user = models.OneToOneField(
        "User", on_delete=models.CASCADE,
        related_name="customer_profile",
        help_text="Linked user account (role must be 'customer').",
    )
    brand_name      = models.CharField(max_length=200, help_text="Trading name of the brand.")
    contact_name    = models.CharField(max_length=150, help_text="Primary point of contact.")
    phone           = models.CharField(max_length=20,  help_text="Primary phone with country code.")
    alternate_phone = models.CharField(max_length=20, null=True, blank=True,
                                        help_text="Secondary contact number.")
    address_line1   = models.TextField(null=True, blank=True, help_text="Street address.")
    address_line2   = models.TextField(null=True, blank=True, help_text="Area / landmark.")
    city            = models.CharField(max_length=100, null=True, blank=True)
    state           = models.CharField(max_length=100, null=True, blank=True)
    pin_code        = models.CharField(max_length=12,  null=True, blank=True)
    country         = models.CharField(max_length=80,  default="India")
    profile_picture = models.ImageField(
        upload_to="customers/profile_pictures/",
        null=True, blank=True,
        help_text="Customer profile picture.",
    )
    created_by_admin = models.ForeignKey(
        "User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_customers",
        help_text="Which admin created this account.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = "customers"
        verbose_name        = "Customer"
        verbose_name_plural = "Customers"
        indexes = [
            models.Index(fields=["brand_name"], name="idx_customers_brand"),
        ]

    def __str__(self):
        return f"{self.brand_name} ({self.user.email})"

    def full_address(self) -> str:
        parts = [
            self.address_line1, self.address_line2,
            self.city, self.state, self.pin_code, self.country,
        ]
        return ", ".join(p for p in parts if p)