from django.db import models

# Create your models here.
import uuid
from django.db import models
from django.conf import settings


class Enquiry(models.Model):
    ORDER_TYPE_CHOICES = [
        ('private_label', 'Private Label'),
        ('white_label', 'White Label'),
        ('fabrics', 'Fabrics'),
        ('others', 'Others'),
    ]

    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('waiting_response', 'Waiting Response'),
        ('prospect', 'Prospect'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('closed', 'Closed'),
    ]

    SOURCE_PAGE_CHOICES = [
        ('general', 'General'),
        ('private_label_page', 'Private Label Page'),
        ('white_label_page', 'White Label Page'),
        ('fabrics_page', 'Fabrics Page'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enquiry_number = models.CharField(max_length=20, unique=True, blank=True)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    email = models.EmailField(max_length=255)
    brand_name = models.CharField(max_length=200)
    company_age_years = models.SmallIntegerField(null=True, blank=True)
    total_pieces_required = models.IntegerField(null=True, blank=True)
    annual_revenue = models.BigIntegerField(null=True, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    assigned_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_enquiries'
    )
    is_viewed = models.BooleanField(default=False)
    viewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(null=True, blank=True)
    customer = models.ForeignKey(
        'accounts.Customer',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='enquiries'
    )
    source_page = models.CharField(max_length=50, choices=SOURCE_PAGE_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.enquiry_number:
            from django.utils import timezone
            year = timezone.now().year
            count = Enquiry.objects.filter(created_at__year=year).count() + 1
            self.enquiry_number = f"ENQ-{year}-{count:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.enquiry_number


class EnquiryImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name='images')
    storage_path = models.TextField()
    file_name = models.CharField(max_length=255)
    file_size_bytes = models.IntegerField()
    mime_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} ({self.enquiry.enquiry_number})"