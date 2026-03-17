import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


class PaymentType(models.TextChoices):
    ORDER = "order", "Order"
    EBOOK = "ebook", "E-Book"


class PaymentTransaction(models.Model):
    """
    Generic payment transaction — works for Orders, E-Books, or any future payment.
    Uses GenericForeignKey so it can link to any model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Generic FK — links to any model (Order, EBook purchase etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type","object_id")

    # Payment type — for easy filtering
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices, help_text="What is being paid for")

    # Who paid
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments")

    # Amount
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default="INR")

    # Status
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)

    # Razorpay fields
    razorpay_order_id = models.CharField(max_length=100, unique=True, help_text="Razorpay order ID")
    payment_reference = models.CharField(max_length=100, null=True, blank=True, help_text="Razorpay payment ID after success")
    razorpay_signature = models.CharField(max_length=255, null=True, blank=True, help_text="Razorpay signature for verification")

    # Notes
    notes = models.TextField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True, help_text="Reason if payment failed")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_transactions"
        ordering = ["-created_at"]
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"
        indexes = [
            models.Index(fields=["status"], name="idx_payment_status"),
            models.Index(fields=["payment_type"], name="idx_payment_type"),
            models.Index(fields=["razorpay_order_id"], name="idx_razorpay_order"),
        ]

    def __str__(self):
        return f"{self.payment_type} | {self.amount} {self.currency} | {self.status}"