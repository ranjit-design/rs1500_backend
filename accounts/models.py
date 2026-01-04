# accounts/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone

class EmailOTP(models.Model):
    email = models.EmailField(db_index=True)
    otp_hash = models.CharField(max_length=128)
    salt = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.expires_at


class HotelAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hotel_account",
    )
    hotel = models.OneToOneField(
        "hotels.Hotel",
        on_delete=models.CASCADE,
        related_name="account",
    )

    def __str__(self):
        return f"HotelAccount(hotel_id={self.hotel_id}, user_id={self.user_id})"
