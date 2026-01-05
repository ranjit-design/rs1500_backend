from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotels", "0010_remove_hotel_latitude_longitude_state_only"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hotel",
            name="is_active",
            field=models.BooleanField(default=False),
        ),
    ]
