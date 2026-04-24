from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_passwordresetotp"),
    ]

    operations = [
        migrations.AddField(
            model_name="passwordresetotp",
            name="otp_hash",
            field=models.CharField(default="", max_length=64),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name="passwordresetotp",
            name="otp",
        ),
    ]
