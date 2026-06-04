from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0004_fabricscatalogue_fabricscatalogueimage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='wlprototype',
            name='description',
            field=models.TextField(blank=True, help_text='Additional style details to show on the product page', null=True),
        ),
    ]
