from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_customer_profile_picture_alter_customer_city_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordResetOTP",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("otp", models.CharField(max_length=6)),
                ("reset_token", models.CharField(blank=True, max_length=64)),
                ("is_verified", models.BooleanField(default=False)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reset_otps",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "password_reset_otps", "ordering": ["-created_at"]},
        ),
    ]
