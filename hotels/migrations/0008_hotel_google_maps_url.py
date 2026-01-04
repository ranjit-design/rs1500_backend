from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotels", "0007_hotel_approval_requested"),
    ]

    operations = [
        migrations.AddField(
            model_name="hotel",
            name="google_maps_url",
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
