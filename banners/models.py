import uuid
from django.db import models


class Banner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    title      = models.CharField(max_length=200, null=True, blank=True, help_text="Optional banner title")
    image      = models.ImageField(upload_to="banners/", help_text="Banner image")
    link_url   = models.URLField(max_length=500, null=True, blank=True, help_text="Optional click-through URL")
    is_active  = models.BooleanField(default=True, help_text="Controls visibility on the app")
    sort_order = models.SmallIntegerField(default=0, help_text="Lower numbers appear first")

    created_by = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="created_banners",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "banners"
        ordering = ["sort_order", "-created_at"]
        verbose_name = "Banner"
        verbose_name_plural = "Banners"

    def __str__(self):
        return self.title or f"Banner {self.id}"
