from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django import forms

from .models import (
    Amenity,
    Booking,
    Hotel,
    HotelFacility,
    HotelFacilityMapping,
    HotelImage,
    HotelPolicy,
    Review,
    RoomImage,
    RoomType,
)


class AmenityAdminForm(forms.ModelForm):
    hotels = forms.ModelMultipleChoiceField(
        queryset=Hotel.objects.all().order_by("name"),
        required=False,
    )

    class Meta:
        model = Amenity
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if getattr(self, "instance", None) and getattr(self.instance, "pk", None):
            self.fields["hotels"].initial = self.instance.hotels.all()


class AmenityActionForm(ActionForm):
    hotel = forms.ModelChoiceField(
        queryset=Hotel.objects.all().order_by("name"),
        required=False,
        label="Hotel",
    )


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    form = AmenityAdminForm
    action_form = AmenityActionForm
    actions = ["add_selected_amenities_to_hotel", "add_all_amenities_to_hotel"]

    def add_selected_amenities_to_hotel(self, request, queryset):
        hotel = request.POST.get("hotel")
        if not hotel:
            self.message_user(request, "Please choose a hotel.", level=messages.ERROR)
            return

        hotel_obj = Hotel.objects.filter(pk=hotel).first()
        if not hotel_obj:
            self.message_user(request, "Invalid hotel selected.", level=messages.ERROR)
            return

        amenities = list(queryset)
        if not amenities:
            self.message_user(request, "No amenities selected.", level=messages.WARNING)
            return

        hotel_obj.amenities.add(*amenities)
        self.message_user(
            request,
            f"Added {len(amenities)} amenity(s) to hotel '{hotel_obj.name}'.",
            level=messages.SUCCESS,
        )

    add_selected_amenities_to_hotel.short_description = "Add selected amenities to chosen hotel"

    def add_all_amenities_to_hotel(self, request, queryset):
        hotel = request.POST.get("hotel")
        if not hotel:
            self.message_user(request, "Please choose a hotel.", level=messages.ERROR)
            return

        hotel_obj = Hotel.objects.filter(pk=hotel).first()
        if not hotel_obj:
            self.message_user(request, "Invalid hotel selected.", level=messages.ERROR)
            return

        amenities = list(Amenity.objects.all())
        if not amenities:
            self.message_user(request, "No amenities exist to add.", level=messages.WARNING)
            return

        hotel_obj.amenities.add(*amenities)
        self.message_user(
            request,
            f"Added all ({len(amenities)}) amenity(s) to hotel '{hotel_obj.name}'.",
            level=messages.SUCCESS,
        )

    add_all_amenities_to_hotel.short_description = "Add ALL amenities to chosen hotel"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        hotels = form.cleaned_data.get("hotels")
        if hotels is not None:
            obj.hotels.set(hotels)


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    filter_horizontal = ("amenities",)
    actions = ["add_all_amenities"]
    list_display = ("name", "city", "country", "is_active", "rating")
    search_fields = ("name", "city", "country", "address")
    list_filter = ("is_active", "country", "city")
    ordering = ("name",)

    def add_all_amenities(self, request, queryset):
        amenities = list(Amenity.objects.all())
        if not amenities:
            self.message_user(request, "No amenities exist to add.", level=messages.WARNING)
            return

        updated = 0
        for hotel in queryset:
            hotel.amenities.add(*amenities)
            updated += 1

        self.message_user(
            request,
            f"Added all amenities to {updated} hotel(s).",
            level=messages.SUCCESS,
        )

    add_all_amenities.short_description = "Add ALL amenities to selected hotel(s)"


admin.site.register(HotelImage)
admin.site.register(RoomType)
admin.site.register(Booking)
admin.site.register(Review)
admin.site.register(HotelPolicy)
admin.site.register(RoomImage)
admin.site.register(HotelFacility)
admin.site.register(HotelFacilityMapping)
