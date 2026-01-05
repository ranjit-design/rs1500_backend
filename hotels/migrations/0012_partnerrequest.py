from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotels", "0011_alter_hotel_is_active_default"),
    ]

    operations = [
        migrations.CreateModel(
            name="PartnerRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=120)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("hotel_name", models.CharField(max_length=200)),
                ("country", models.CharField(blank=True, max_length=80)),
                ("city", models.CharField(blank=True, max_length=80)),
                ("message", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("contacted", "Contacted"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        default="new",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
