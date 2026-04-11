import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Banner",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(blank=True, max_length=200, null=True, help_text="Optional banner title")),
                ("image", models.ImageField(upload_to="banners/", help_text="Banner image")),
                ("link_url", models.URLField(blank=True, max_length=500, null=True, help_text="Optional click-through URL")),
                ("is_active", models.BooleanField(default=True, help_text="Controls visibility on the app")),
                ("sort_order", models.SmallIntegerField(default=0, help_text="Lower numbers appear first")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_banners",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Banner",
                "verbose_name_plural": "Banners",
                "db_table": "banners",
                "ordering": ["sort_order", "-created_at"],
            },
        ),
    ]
