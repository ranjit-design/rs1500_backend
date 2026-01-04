from django.contrib import admin, messages
from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.admin.helpers import ActionForm
from django import forms
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .models import (
    Amenity,
    Booking,
    Hotel,
    HotelFacility,
    HotelFacilityMapping,
    HotelImage,
    HotelPolicy,
    Reservation,
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
admin.site.register(Reservation)
admin.site.register(Review)
admin.site.register(HotelPolicy)
admin.site.register(RoomImage)
admin.site.register(HotelFacility)
admin.site.register(HotelFacilityMapping)


def get_user_hotel_for_admin(request):
    user = getattr(request, "user", None)
    account = getattr(user, "hotel_account", None)
    return getattr(account, "hotel", None)


class HotelInfoForm(forms.ModelForm):
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all().order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Hotel
        fields = [
            "name",
            "place_type",
            "city",
            "country",
            "address",
            "google_maps_url",
        ]

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        super().__init__(*args, **kwargs)
        if instance is not None:
            self.fields["amenities"].initial = instance.amenities.all()


class HotelDetailsForm(forms.ModelForm):
    class Meta:
        model = Hotel
        fields = [
            "name",
            "place_type",
            "city",
            "country",
            "address",
            "google_maps_url",
        ]


class HotelAmenitiesForm(forms.Form):
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all().order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )


class HotelImageForm(forms.ModelForm):
    class Meta:
        model = HotelImage
        fields = ["image_url", "is_cover", "sort_order"]


class RoomTypeForm(forms.ModelForm):
    class Meta:
        model = RoomType
        fields = [
            "name",
            "price_per_night",
            "currency",
            "total_rooms",
            "max_adults",
            "max_children",
            "is_active",
        ]

    def save(self, commit=True):
        obj = super().save(commit=False)
        max_adults = self.cleaned_data.get("max_adults") or 0
        max_children = self.cleaned_data.get("max_children") or 0
        obj.max_guests = max_adults + max_children
        if commit:
            obj.save()
        return obj


class HotelPolicyForm(forms.ModelForm):
    class Meta:
        model = HotelPolicy
        fields = [
            "check_in_time",
            "check_out_time",
            "cancellation_policy",
            "payment_policy",
            "child_policy",
            "pet_policy",
            "additional_info",
        ]
        widgets = {
            "check_in_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "check_out_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "cancellation_policy": forms.Textarea(attrs={"rows": 4}),
            "payment_policy": forms.Textarea(attrs={"rows": 4}),
            "child_policy": forms.Textarea(attrs={"rows": 3}),
            "pet_policy": forms.Textarea(attrs={"rows": 3}),
            "additional_info": forms.Textarea(attrs={"rows": 3}),
        }


class RoomImageForm(forms.ModelForm):
    from_gallery = forms.ModelChoiceField(
        queryset=HotelImage.objects.none(),
        required=False,
        label="Choose from hotel gallery",
    )

    class Meta:
        model = RoomImage
        fields = ["image_url", "caption", "is_primary", "sort_order"]

    def __init__(self, *args, **kwargs):
        hotel = kwargs.pop("hotel", None)
        super().__init__(*args, **kwargs)
        if hotel is not None:
            self.fields["from_gallery"].queryset = HotelImage.objects.filter(hotel=hotel).order_by(
                "sort_order", "id"
            )


class HotelPartnerAuthenticationForm(AdminAuthenticationForm):
    """Custom auth form that allows non-staff hotel accounts into hotel-admin."""

    def confirm_login_allowed(self, user):
        # Allow active users that have an associated HotelAccount
        if getattr(user, "is_active", False) and hasattr(user, "hotel_account"):
            return

        # Fallback to default admin behaviour for staff/superusers
        super().confirm_login_allowed(user)


class HotelPartnerAdminSite(AdminSite):
    site_header = "Hotel Partner Portal"
    site_title = "Hotel Partner Portal"
    index_title = "Manage your hotel"
    login_form = HotelPartnerAuthenticationForm

    def has_permission(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_active", False) and hasattr(user, "hotel_account"):
            return True
        return bool(getattr(user, "is_staff", False) and getattr(user, "is_superuser", False))

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "",
                self.admin_view(self.dashboard_view),
                name="hotel_dashboard",
            ),
            path(
                "hotel-details/",
                self.admin_view(self.manage_hotel_details_view),
                name="manage_hotel_details",
            ),
            path(
                "images/",
                self.admin_view(self.manage_images_view),
                name="manage_images",
            ),
            path(
                "amenities/",
                self.admin_view(self.manage_amenities_view),
                name="manage_amenities",
            ),
            path(
                "hotel-info/",
                self.admin_view(self.manage_hotel_info_view),
                name="manage_hotel_info",
            ),
            path(
                "rooms/",
                self.admin_view(self.manage_rooms_view),
                name="manage_rooms",
            ),
            path(
                "rooms/<int:room_type_id>/photos/",
                self.admin_view(self.manage_room_photos_view),
                name="manage_room_photos",
            ),
            path(
                "policies/",
                self.admin_view(self.manage_policies_view),
                name="manage_policies",
            ),
            path(
                "reservations/",
                self.admin_view(self.manage_reservations_view),
                name="manage_reservations",
            ),
        ]
        return custom_urls + urls

    def _get_hotel_for_request(self, request):
        hotel = get_user_hotel_for_admin(request)
        if hotel:
            return hotel
        if getattr(request.user, "is_superuser", False):
            hotel_id = request.GET.get("hotel_id")
            if hotel_id:
                return Hotel.objects.filter(pk=hotel_id).first()
        return None

    def dashboard_view(self, request):
        hotel = self._get_hotel_for_request(request)
        context = dict(
            self.each_context(request),
            title="Hotel Partner Dashboard",
            hotel=hotel,
            manage_hotel_details_url=reverse("hotel_partner_admin:manage_hotel_details"),
            manage_images_url=reverse("hotel_partner_admin:manage_images"),
            manage_amenities_url=reverse("hotel_partner_admin:manage_amenities"),
            manage_hotel_info_url=reverse("hotel_partner_admin:manage_hotel_info"),
            manage_rooms_url=reverse("hotel_partner_admin:manage_rooms"),
            manage_policies_url=reverse("hotel_partner_admin:manage_policies"),
            manage_reservations_url=reverse("hotel_partner_admin:manage_reservations"),
        )
        return TemplateResponse(request, "hotels/hotel_dashboard.html", context)

    def manage_hotel_details_view(self, request):
        hotel = self._get_hotel_for_request(request)
        if not hotel:
            messages.error(request, "No hotel is associated with this account.")
            return redirect("hotel_partner_admin:hotel_dashboard")

        if request.method == "POST":
            form = HotelDetailsForm(request.POST, instance=hotel)
            if form.is_valid():
                form.save()
                messages.success(request, "Hotel details updated.")
                return redirect("hotel_partner_admin:manage_hotel_details")
        else:
            form = HotelDetailsForm(instance=hotel)

        context = dict(
            self.each_context(request),
            title="Hotel Details",
            hotel=hotel,
            form=form,
        )
        return TemplateResponse(request, "hotels/manage_hotel_details.html", context)

    def manage_images_view(self, request):
        hotel = self._get_hotel_for_request(request)
        if not hotel:
            messages.error(request, "No hotel is associated with this account.")
            return redirect("hotel_partner_admin:hotel_dashboard")

        if request.method == "POST":
            action = request.POST.get("action")
            if action == "add_photo":
                image_form = HotelImageForm(request.POST)
                if image_form.is_valid():
                    image = image_form.save(commit=False)
                    image.hotel = hotel
                    image.save()
                    messages.success(request, "Photo added.")
                    return redirect("hotel_partner_admin:manage_images")
            elif action == "delete_photo":
                image_id = request.POST.get("image_id")
                if image_id:
                    HotelImage.objects.filter(pk=image_id, hotel=hotel).delete()
                    messages.success(request, "Photo deleted.")
                    return redirect("hotel_partner_admin:manage_images")
            image_form = HotelImageForm()
        else:
            image_form = HotelImageForm()

        images = HotelImage.objects.filter(hotel=hotel).order_by("sort_order", "id")

        context = dict(
            self.each_context(request),
            title="Hotel Images",
            hotel=hotel,
            image_form=image_form,
            images=images,
        )
        return TemplateResponse(request, "hotels/manage_hotel_images.html", context)

    def manage_amenities_view(self, request):
        hotel = self._get_hotel_for_request(request)
        if not hotel:
            messages.error(request, "No hotel is associated with this account.")
            return redirect("hotel_partner_admin:hotel_dashboard")

        if request.method == "POST":
            form = HotelAmenitiesForm(request.POST)
            if form.is_valid():
                hotel.amenities.set(form.cleaned_data.get("amenities") or [])
                messages.success(request, "Amenities updated.")
                return redirect("hotel_partner_admin:manage_amenities")
        else:
            form = HotelAmenitiesForm(initial={"amenities": hotel.amenities.all()})

        context = dict(
            self.each_context(request),
            title="Hotel Amenities",
            hotel=hotel,
            form=form,
        )
        return TemplateResponse(request, "hotels/manage_hotel_amenities.html", context)

    def manage_hotel_info_view(self, request):
        hotel = self._get_hotel_for_request(request)
        if not hotel:
            messages.error(request, "No hotel is associated with this account.")
            return redirect("hotel_partner_admin:hotel_dashboard")

        if request.method == "POST":
            action = request.POST.get("action")
            if action == "save_info":
                form = HotelInfoForm(request.POST, instance=hotel)
                image_form = HotelImageForm()
                if form.is_valid():
                    hotel = form.save()
                    amenities = form.cleaned_data.get("amenities")
                    if amenities is not None:
                        hotel.amenities.set(amenities)
                    messages.success(request, "Hotel information updated.")
                    return redirect("hotel_partner_admin:manage_hotel_info")
            elif action == "add_photo":
                form = HotelInfoForm(instance=hotel)
                image_form = HotelImageForm(request.POST)
                if image_form.is_valid():
                    image = image_form.save(commit=False)
                    image.hotel = hotel
                    image.save()
                    messages.success(request, "Photo added.")
                    return redirect("hotel_partner_admin:manage_hotel_info")
            elif action == "delete_photo":
                form = HotelInfoForm(instance=hotel)
                image_form = HotelImageForm()
                image_id = request.POST.get("image_id")
                if image_id:
                    HotelImage.objects.filter(pk=image_id, hotel=hotel).delete()
                    messages.success(request, "Photo deleted.")
                    return redirect("hotel_partner_admin:manage_hotel_info")
            else:
                form = HotelInfoForm(instance=hotel)
                image_form = HotelImageForm()
        else:
            form = HotelInfoForm(instance=hotel)
            image_form = HotelImageForm()

        images = HotelImage.objects.filter(hotel=hotel).order_by("sort_order", "id")

        context = dict(
            self.each_context(request),
            title="Manage Hotel Information",
            hotel=hotel,
            form=form,
            image_form=image_form,
            images=images,
        )
        return TemplateResponse(request, "hotels/manage_hotel_info.html", context)

    def manage_rooms_view(self, request):
        hotel = self._get_hotel_for_request(request)
        if not hotel:
            messages.error(request, "No hotel is associated with this account.")
            return redirect("hotel_partner_admin:hotel_dashboard")

        if request.method == "POST":
            action = request.POST.get("action")
            if action == "add_room_type":
                form = RoomTypeForm(request.POST)
                if form.is_valid():
                    room_type = form.save(commit=False)
                    room_type.hotel = hotel
                    room_type.save()
                    messages.success(request, "Room type added.")
                    return redirect("hotel_partner_admin:manage_rooms")
            elif action == "delete_room_type":
                room_type_id = request.POST.get("room_type_id")
                if room_type_id:
                    RoomType.objects.filter(pk=room_type_id, hotel=hotel).delete()
                    messages.success(request, "Room type deleted.")
                    return redirect("hotel_partner_admin:manage_rooms")
            else:
                form = RoomTypeForm()
        else:
            form = RoomTypeForm()

        room_types = RoomType.objects.filter(hotel=hotel).order_by("name")

        context = dict(
            self.each_context(request),
            title="Manage Rooms",
            hotel=hotel,
            form=form,
            room_types=room_types,
        )
        return TemplateResponse(request, "hotels/manage_rooms.html", context)

    def manage_room_photos_view(self, request, room_type_id):
        hotel = self._get_hotel_for_request(request)
        if not hotel:
            messages.error(request, "No hotel is associated with this account.")
            return redirect("hotel_partner_admin:hotel_dashboard")

        try:
            room_type = RoomType.objects.get(pk=room_type_id, hotel=hotel)
        except RoomType.DoesNotExist:
            messages.error(request, "This room type does not belong to your hotel.")
            return redirect("hotel_partner_admin:manage_rooms")

        if request.method == "POST":
            action = request.POST.get("action")
            if action == "add_photo":
                form = RoomImageForm(request.POST, hotel=hotel)
                if form.is_valid():
                    image = form.save(commit=False)
                    gallery_source = form.cleaned_data.get("from_gallery")
                    if gallery_source is not None:
                        image.image_url = gallery_source.image_url
                    image.room_type = room_type
                    image.save()
                    messages.success(request, "Room photo added.")
                    return redirect(
                        "hotel_partner_admin:manage_room_photos", room_type_id=room_type.id
                    )
            elif action == "delete_photo":
                image_id = request.POST.get("image_id")
                if image_id:
                    RoomImage.objects.filter(
                        pk=image_id,
                        room_type__hotel=hotel,
                        room_type=room_type,
                    ).delete()
                    messages.success(request, "Room photo deleted.")
                    return redirect(
                        "hotel_partner_admin:manage_room_photos", room_type_id=room_type.id
                    )
            else:
                form = RoomImageForm(hotel=hotel)
        else:
            form = RoomImageForm(hotel=hotel)

        images = RoomImage.objects.filter(room_type=room_type).order_by("sort_order", "id")
        gallery_images = HotelImage.objects.filter(hotel=hotel).order_by("sort_order", "id")

        context = dict(
            self.each_context(request),
            title=f"Manage Photos - {room_type.name}",
            hotel=hotel,
            room_type=room_type,
            form=form,
            images=images,
            gallery_images=gallery_images,
        )
        return TemplateResponse(request, "hotels/manage_room_photos.html", context)

    def manage_policies_view(self, request):
        hotel = self._get_hotel_for_request(request)
        if not hotel:
            messages.error(request, "No hotel is associated with this account.")
            return redirect("hotel_partner_admin:hotel_dashboard")

        policy = getattr(hotel, "policies", None)

        if request.method == "POST":
            form = HotelPolicyForm(request.POST, instance=policy)
            if form.is_valid():
                policy = form.save(commit=False)
                policy.hotel = hotel
                policy.save()
                messages.success(request, "Policies saved.")
                return redirect("hotel_partner_admin:manage_policies")
        else:
            form = HotelPolicyForm(instance=policy)

        context = dict(
            self.each_context(request),
            title="Manage Hotel Policies",
            hotel=hotel,
            form=form,
        )
        return TemplateResponse(request, "hotels/manage_policies.html", context)

    def manage_reservations_view(self, request):
        """List and manage reservation status for the partner's hotel."""
        hotel = self._get_hotel_for_request(request)
        if not hotel:
            messages.error(request, "No hotel is associated with this account.")
            return redirect("hotel_partner_admin:hotel_dashboard")

        if request.method == "POST":
            action = request.POST.get("action")
            if action == "update_status":
                reservation_id = request.POST.get("reservation_id")
                new_status = request.POST.get("status")

                valid_statuses = {
                    Reservation.Status.PENDING,
                    Reservation.Status.CONFIRMED,
                    Reservation.Status.CANCELLED,
                }

                if reservation_id and new_status in valid_statuses:
                    try:
                        reservation = Reservation.objects.get(pk=reservation_id, hotel=hotel)
                    except Reservation.DoesNotExist:
                        messages.error(request, "This reservation does not belong to your hotel.")
                    else:
                        if reservation.status != new_status:
                            reservation.status = new_status
                            reservation.save(update_fields=["status"])
                            messages.success(
                                request,
                                f"Reservation status updated to {reservation.get_status_display()}.",
                            )
                else:
                    messages.error(request, "Invalid reservation or status.")

                return redirect("hotel_partner_admin:manage_reservations")

        reservations = (
            Reservation.objects.filter(hotel=hotel)
            .select_related("room_type")
            .order_by("-created_at")
        )

        context = dict(
            self.each_context(request),
            title="Manage Reservations & Booking Status",
            hotel=hotel,
            reservations=reservations,
        )
        return TemplateResponse(request, "hotels/manage_reservations.html", context)


hotel_partner_admin_site = HotelPartnerAdminSite(name="hotel_partner_admin")


class HotelPartnerHotelAdmin(admin.ModelAdmin):
    filter_horizontal = ("amenities",)
    list_display = ("name", "city", "country", "is_active", "rating")
    search_fields = ("name", "city", "country", "address")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        hotel = get_user_hotel_for_admin(request)
        if hotel:
            return qs.filter(pk=hotel.pk)
        return qs.none()

    def has_add_permission(self, request):
        if not request.user.is_superuser:
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)


class HotelPartnerRoomTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "hotel", "price_per_night", "currency", "total_rooms", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        hotel = get_user_hotel_for_admin(request)
        if hotel:
            return qs.filter(hotel=hotel)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "hotel" and not request.user.is_superuser:
            hotel = get_user_hotel_for_admin(request)
            if hotel:
                kwargs["queryset"] = Hotel.objects.filter(pk=hotel.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            hotel = get_user_hotel_for_admin(request)
            if hotel:
                obj.hotel = hotel
        super().save_model(request, obj, form, change)


class HotelPartnerHotelImageAdmin(admin.ModelAdmin):
    list_display = ("hotel", "image_url", "is_cover", "sort_order")
    list_filter = ("is_cover",)
    search_fields = ("image_url",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        hotel = get_user_hotel_for_admin(request)
        if hotel:
            return qs.filter(hotel=hotel)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "hotel" and not request.user.is_superuser:
            hotel = get_user_hotel_for_admin(request)
            if hotel:
                kwargs["queryset"] = Hotel.objects.filter(pk=hotel.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            hotel = get_user_hotel_for_admin(request)
            if hotel:
                obj.hotel = hotel
        super().save_model(request, obj, form, change)


class HotelPartnerRoomImageAdmin(admin.ModelAdmin):
    list_display = ("room_type", "image_url", "is_primary", "sort_order")
    list_filter = ("is_primary",)
    search_fields = ("image_url", "room_type__name")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        hotel = get_user_hotel_for_admin(request)
        if hotel:
            return qs.filter(room_type__hotel=hotel)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "room_type" and not request.user.is_superuser:
            hotel = get_user_hotel_for_admin(request)
            if hotel:
                kwargs["queryset"] = RoomType.objects.filter(hotel=hotel)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class HotelPartnerHotelPolicyAdmin(admin.ModelAdmin):
    list_display = ("hotel", "check_in_time", "check_out_time")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        hotel = get_user_hotel_for_admin(request)
        if hotel:
            return qs.filter(hotel=hotel)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "hotel" and not request.user.is_superuser:
            hotel = get_user_hotel_for_admin(request)
            if hotel:
                kwargs["queryset"] = Hotel.objects.filter(pk=hotel.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            hotel = get_user_hotel_for_admin(request)
            if hotel:
                obj.hotel = hotel
        super().save_model(request, obj, form, change)


class HotelPartnerFacilityMappingAdmin(admin.ModelAdmin):
    list_display = ("hotel", "facility", "is_available")
    list_filter = ("is_available", "facility__category")
    search_fields = ("facility__name",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        hotel = get_user_hotel_for_admin(request)
        if hotel:
            return qs.filter(hotel=hotel)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "hotel" and not request.user.is_superuser:
            hotel = get_user_hotel_for_admin(request)
            if hotel:
                kwargs["queryset"] = Hotel.objects.filter(pk=hotel.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            hotel = get_user_hotel_for_admin(request)
            if hotel:
                obj.hotel = hotel
        super().save_model(request, obj, form, change)


class HotelPartnerFacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    list_filter = ("category",)
    search_fields = ("name",)

    def has_add_permission(self, request):
        if not request.user.is_superuser:
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)


class HotelPartnerReviewAdmin(admin.ModelAdmin):
    list_display = ("hotel", "user", "rating", "created_at")
    search_fields = ("user__email", "user__username", "hotel__name")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        hotel = get_user_hotel_for_admin(request)
        if hotel:
            return qs.filter(hotel=hotel)
        return qs.none()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
