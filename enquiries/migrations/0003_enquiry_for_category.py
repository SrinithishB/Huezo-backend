from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0002_alter_enquiry_options_alter_enquiryimage_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="enquiry",
            name="for_category",
            field=models.CharField(
                max_length=10,
                choices=[("women", "Women's Wear"), ("men", "Men's Wear"), ("kids", "Kids' Wear")],
                null=True,
                blank=True,
            ),
        ),
    ]
