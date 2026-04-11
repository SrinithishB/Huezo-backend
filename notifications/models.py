# notifications/models.py

import uuid
from django.db import models
from django.conf import settings


class FCMDevice(models.Model):
    """Stores FCM push token per user device."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fcm_devices",
    )
    fcm_token  = models.TextField(unique=True, help_text="Firebase FCM registration token")
    device_id  = models.CharField(
        max_length=200, blank=True,
        help_text="Optional: device identifier to avoid duplicates",
    )
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fcm_devices"
        verbose_name = "FCM Device"
        verbose_name_plural = "FCM Devices"

    def __str__(self):
        return f"{self.user.email} — {self.fcm_token[:20]}..."


class Notification(models.Model):
    """In-app notification log — every push sent is recorded here."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title      = models.CharField(max_length=200)
    body       = models.TextField()
    data       = models.JSONField(default=dict, blank=True,
                                   help_text="Extra payload e.g. order_id, type")
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = "notifications"
        ordering  = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.user.email} — {self.title}"