import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserRole(models.TextChoices):
    ADMIN    = "admin",    "Admin"     # Full access + Django admin panel
    STAFF    = "staff",    "Staff"     # Internal users — NO admin panel access
    CUSTOMER = "customer", "Customer"  # End users — NO admin panel access


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        extra_fields.setdefault("role", UserRole.CUSTOMER)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # Bcrypt-hashed via AUTH_PASSWORD_HASHERS
        user.save(using=self._db)
        return user

    def create_staff_user(self, email, password=None, **extra_fields):
        """Convenience method to create a staff user."""
        extra_fields.setdefault("role", UserRole.STAFF)
        return self.create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Only ADMIN role gets superuser + staff flags (admin panel access)."""
        extra_fields["role"] = UserRole.ADMIN
        extra_fields["is_staff"] = True       # Required for Django admin panel login
        extra_fields["is_superuser"] = True
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    # Primary key
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,help_text="Auto-generated primary key.",)
    
    # Auth fields
    email = models.EmailField( max_length=255,unique=True,help_text="Login email address.",)
    # password field is inherited from AbstractBaseUser (stored as bcrypt hash)

    # Role  —  drives ALL access control
    role = models.CharField(max_length=10,choices=UserRole.choices,default=UserRole.CUSTOMER,
        help_text="'admin' | 'staff' | 'customer' — drives all access control.",)

    # Status
    is_active = models.BooleanField(default=True,help_text="Soft-disable without deleting the record.",)

    # Django admin panel gate — set to True ONLY for admins (see save())
    is_staff = models.BooleanField(default=False,help_text="True only for admin role; controls Django admin panel access.",)

    # Brute-force / lockout
    failed_login_attempts = models.SmallIntegerField(default=0,help_text="Increment on bad password; lock at threshold.",)
    locked_until = models.DateTimeField(null=True,blank=True,help_text="NULL means not locked; set to future datetime on lockout.",)

    # Audit timestamps
    last_login_at = models.DateTimeField(null=True, blank=True, help_text="Updated on every successful login.",)
    created_at = models.DateTimeField(auto_now_add=True,help_text="Record creation timestamp.",)
    updated_at = models.DateTimeField(auto_now=True, help_text="Auto-updated on every save.",)

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    MAX_FAILED_ATTEMPTS = 5  # lock threshold — adjust as needed

    class Meta:
        db_table        = "users"
        verbose_name    = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.email} ({self.role})"

    # Override save() — keep is_staff in sync with role automatically
    def save(self, *args, **kwargs):
        # Only ADMIN role may access the Django admin panel
        self.is_staff = (self.role == UserRole.ADMIN)
        super().save(*args, **kwargs)

    # Role helpers
    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_staff_member(self) -> bool:
        """Use this to check the staff role (not Django's is_staff flag)."""
        return self.role == UserRole.STAFF

    @property
    def is_customer(self) -> bool:
        return self.role == UserRole.CUSTOMER

    # Lockout helpers
    @property
    def is_locked(self) -> bool:
        """Return True if the account is currently locked out."""
        return bool(self.locked_until and self.locked_until > timezone.now())

    def record_failed_login(self, lock_duration_minutes: int = 30) -> None:
        """Increment failed attempts and lock when threshold is reached."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            self.locked_until = timezone.now() + timezone.timedelta(
                minutes=lock_duration_minutes
            )
        self.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])

    def record_successful_login(self) -> None:
        """Reset lockout state and update last_login_at."""
        self.failed_login_attempts = 0
        self.locked_until          = None
        self.last_login_at         = timezone.now()
        self.save(
            update_fields=[
                "failed_login_attempts",
                "locked_until",
                "last_login_at",
                "updated_at",
            ]
        )


class Customer(models.Model):
    # Primary key — also a FK to users table (1-to-1)
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,help_text="1-to-1 with users table.",)
    user = models.OneToOneField("User",on_delete=models.CASCADE,related_name="customer_profile",help_text="Linked user account (role must be 'customer').",)

    # Brand / contact info
    brand_name = models.CharField(max_length=200,help_text="Trading name of the brand.",)
    contact_name = models.CharField(max_length=150,help_text="Primary point of contact.",)
    phone = models.CharField(max_length=20,help_text="Primary phone with country code.",)
    alternate_phone = models.CharField(max_length=20,null=True,blank=True,help_text="Secondary contact number.",)

    # Address
    address_line1 = models.TextField(null=True,blank=True,help_text="Street address.",)
    address_line2 = models.TextField(null=True,blank=True,help_text="Area / landmark.",)
    city = models.CharField(max_length=100,null=True,blank=True,help_text="City.",)
    state = models.CharField(max_length=100,null=True,blank=True,help_text="State / province.",)
    pin_code = models.CharField(max_length=12,null=True,blank=True,help_text="Postal code.",)
    country = models.CharField(max_length=80,default="India",help_text="Country.",)

    # Audit — who created this account
    created_by_admin = models.ForeignKey("User",null=True,blank=True, on_delete=models.SET_NULL,related_name="created_customers",
        help_text="Which admin created this account.",)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers"
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        indexes = [
            models.Index(fields=["brand_name"], name="idx_customers_brand"),
        ]

    def __str__(self):
        return f"{self.brand_name} ({self.user.email})"

    # Helper
    def full_address(self) -> str:
        """Returns a formatted single-line address."""
        parts = [self.address_line1,self.address_line2,self.city,self.state,self.pin_code,self.country,]
        return ", ".join(p for p in parts if p)