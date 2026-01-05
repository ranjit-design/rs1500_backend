from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotels", "0012_partnerrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="guest_address",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
