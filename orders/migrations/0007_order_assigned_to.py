from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_add_swatch_required"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="assigned_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_orders",
                help_text="Staff member responsible for this order",
                limit_choices_to={"role__in": ["admin", "staff"]},
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
