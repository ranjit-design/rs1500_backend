from django.contrib import admin

from .models import EmailOTP, HotelAccount


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at", "expires_at", "used", "attempts")
    list_filter = ("used",)
    search_fields = ("email",)


@admin.register(HotelAccount)
class HotelAccountAdmin(admin.ModelAdmin):
    list_display = ("hotel", "user")
    search_fields = ("hotel__name", "user__username", "user__email")
