from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotels", "0008_hotel_google_maps_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="hotel",
            name="place_type",
            field=models.CharField(
                choices=[
                    ("hotel", "Hotel"),
                    ("resort", "Resort"),
                    ("lodge", "Lodge"),
                    ("apartment", "Apartment"),
                    ("guest_house", "Guest House"),
                    ("home_stay", "Home Stay"),
                    ("campsite", "Campsite"),
                    ("villa", "Villa"),
                ],
                default="hotel",
                max_length=20,
            ),
        ),
    ]
