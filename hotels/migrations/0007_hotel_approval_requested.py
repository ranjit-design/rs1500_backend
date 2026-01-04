from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotels", "0006_remove_hotel_contact_email_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="hotel",
            name="approval_requested",
            field=models.BooleanField(default=False),
        ),
    ]
