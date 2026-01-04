from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("hotels", "0009_hotel_place_type"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(model_name="hotel", name="latitude"),
                migrations.RemoveField(model_name="hotel", name="longitude"),
            ],
        ),
    ]
