import urllib.parse
import urllib.request

from rest_framework import serializers

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


def _normalize_google_maps_url(url):
    url = (url or "").strip()
    if not url:
        return ""

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return url

    host = (parsed.netloc or "").lower()
    if host in {"maps.app.goo.gl", "goo.gl"}:
        # Some short-link endpoints don't support HEAD; fall back to GET.
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(url, method=method)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return (resp.geturl() or url).strip()
            except Exception:
                continue
        return url

    return url


def _google_maps_embed_url(url):
    url = (url or "").strip()
    if not url:
        return ""

    if "/maps/embed" in url or "output=embed" in url:
        return url

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return url

    host = (parsed.netloc or "").lower()
    if host.endswith("google.com") or host.endswith("google.com.np") or host.endswith("google.co"):
        if parsed.query:
            return f"{url}&output=embed"
        return f"{url}?output=embed"

    return url


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ["id", "name", "icon"]


class HotelImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelImage
        fields = ["id", "image_url", "is_cover", "sort_order"]


class HotelImageWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelImage
        fields = ["id", "hotel", "image_url", "is_cover", "sort_order"]


class MediaLibraryItemSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = HotelImage
        fields = ["id", "image_url", "name"]

    def get_name(self, obj):
        url = obj.image_url or ""
        basename = url.rsplit("/", 1)[-1] if url else ""
        return basename or f"Image {obj.id}"


class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = [
            "id",
            "hotel",
            "name",
            "max_adults",
            "max_children",
            "max_guests",
            "price_per_night",
            "currency",
            "total_rooms",
            "is_active",
        ]


class HotelSerializer(serializers.ModelSerializer):
    amenities = AmenitySerializer(many=True, read_only=True)
    images = HotelImageSerializer(many=True, read_only=True)
    room_types = RoomTypeSerializer(many=True, read_only=True)

    class Meta:
        model = Hotel
        fields = [
            "id",
            "name",
            "place_type",
            "country",
            "city",
            "address",
            "rating",
            "is_active",
            "amenities",
            "images",
            "room_types",
            "created_at",
            "updated_at",
        ]


class HotelWriteSerializer(serializers.ModelSerializer):
    amenities = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        write_only=True,
    )
    amenity_ids = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Hotel
        fields = [
            "id",
            "name",
            "description",
            "place_type",
            "country",
            "city",
            "address",
            "google_maps_url",
            "rating",
            "is_active",
            "amenities",
            "amenity_ids",
        ]

    def validate_google_maps_url(self, value):
        return _normalize_google_maps_url(value)

    def get_amenity_ids(self, obj):
        try:
            return list(obj.amenities.values_list("id", flat=True))
        except Exception:
            return []

    def validate_amenities(self, value):
        """Accept amenities as list of ids, list of objects (with id), or list of names."""

        if value in (None, ""):
            return []

        if not isinstance(value, list):
            raise serializers.ValidationError("amenities must be a list")

        amenity_ids = []
        amenity_names = []
        for item in value:
            if item is None or item == "":
                continue

            if isinstance(item, int):
                amenity_ids.append(item)
                continue

            if isinstance(item, str):
                s = item.strip()
                if not s:
                    continue
                if s.isdigit():
                    amenity_ids.append(int(s))
                else:
                    amenity_names.append(s)
                continue

            if isinstance(item, dict):
                raw_id = item.get("id")
                if raw_id is not None and str(raw_id).strip() != "":
                    try:
                        amenity_ids.append(int(raw_id))
                    except (TypeError, ValueError):
                        raise serializers.ValidationError("Invalid amenity id")
                    continue
                raw_name = item.get("name")
                if raw_name is not None and str(raw_name).strip() != "":
                    amenity_names.append(str(raw_name).strip())
                    continue
                raise serializers.ValidationError("Amenity object must include id or name")

            raise serializers.ValidationError("Invalid amenity value")

        qs = Amenity.objects.all()
        resolved = []

        if amenity_ids:
            found_by_id = list(qs.filter(id__in=list(set(amenity_ids))))
            found_ids = {a.id for a in found_by_id}
            missing_ids = sorted({i for i in amenity_ids if i not in found_ids})
            if missing_ids:
                raise serializers.ValidationError(
                    f"Unknown amenity id(s): {', '.join(map(str, missing_ids))}"
                )
            resolved.extend(found_by_id)

        if amenity_names:
            # Resolve case-insensitively, and auto-create unknown names.
            unique_names = []
            seen_names = set()
            for n in amenity_names:
                key = n.strip().lower()
                if not key or key in seen_names:
                    continue
                seen_names.add(key)
                unique_names.append(n.strip())

            for n in unique_names:
                existing = qs.filter(name__iexact=n).first()
                if existing:
                    resolved.append(existing)
                    continue
                created, _ = Amenity.objects.get_or_create(name=n)
                resolved.append(created)

        # Deduplicate while keeping stable order
        seen = set()
        unique = []
        for a in resolved:
            if a.id in seen:
                continue
            seen.add(a.id)
            unique.append(a)
        return unique

    def create(self, validated_data):
        amenities = validated_data.pop("amenities", None)
        instance = super().create(validated_data)
        if amenities is not None:
            instance.amenities.set(amenities)
        return instance

    def update(self, instance, validated_data):
        amenities = validated_data.pop("amenities", None)
        instance = super().update(instance, validated_data)
        if amenities is not None:
            instance.amenities.set(amenities)
        return instance


class BookingSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "user",
            "hotel",
            "room_type",
            "check_in",
            "check_out",
            "adults",
            "children",
            "rooms_count",
            "total_price",
            "status",
            "created_at",
        ]
        read_only_fields = ["user", "total_price", "status", "created_at"]

    def validate(self, attrs):
        check_in = attrs.get("check_in")
        check_out = attrs.get("check_out")
        room_type = attrs.get("room_type")
        rooms_count = attrs.get("rooms_count", 1)

        if check_in and check_out and check_out <= check_in:
            raise serializers.ValidationError("check_out must be after check_in")

        if room_type and attrs.get("hotel") and room_type.hotel_id != attrs["hotel"].id:
            raise serializers.ValidationError("room_type does not belong to this hotel")

        if rooms_count <= 0:
            raise serializers.ValidationError("rooms_count must be >= 1")

        if check_in and check_out and room_type:
            nights = (check_out - check_in).days
            attrs["total_price"] = room_type.price_per_night * nights * rooms_count

        return attrs


class RoomImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomImage
        fields = ["id", "room_type", "image_url", "is_primary", "caption", "sort_order"]


class RoomTypeWithImagesSerializer(serializers.ModelSerializer):
    room_images = RoomImageSerializer(many=True, read_only=True)

    class Meta:
        model = RoomType
        fields = [
            "id",
            "hotel",
            "name",
            "max_adults",
            "max_children",
            "max_guests",
            "price_per_night",
            "currency",
            "total_rooms",
            "is_active",
            "room_images",
        ]


class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "hotel",
            "user",
            "rating",
            "title",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]


class HotelPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelPolicy
        fields = [
            "id",
            "hotel",
            "check_in_time",
            "check_out_time",
            "cancellation_policy",
            "payment_policy",
            "child_policy",
            "pet_policy",
            "additional_info",
        ]


class HotelFacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelFacility
        fields = ["id", "name", "category", "icon_class"]


class HotelFacilityMappingSerializer(serializers.ModelSerializer):
    facility = HotelFacilitySerializer(read_only=True)
    facility_id = serializers.PrimaryKeyRelatedField(
        source="facility",
        queryset=HotelFacility.objects.all(),
        write_only=True,
    )

    class Meta:
        model = HotelFacilityMapping
        fields = ["id", "hotel", "facility", "facility_id", "description", "is_available"]


class HotelDetailSerializer(serializers.ModelSerializer):
    amenities = AmenitySerializer(many=True, read_only=True)
    images = HotelImageSerializer(many=True, read_only=True)
    room_types = RoomTypeWithImagesSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    policies = HotelPolicySerializer(read_only=True)
    google_maps_embed_url = serializers.SerializerMethodField(read_only=True)

    def get_google_maps_embed_url(self, obj):
        return _google_maps_embed_url(getattr(obj, "google_maps_url", ""))

    class Meta:
        model = Hotel
        fields = [
            "id",
            "name",
            "description",
            "place_type",
            "country",
            "city",
            "address",
            "google_maps_url",
            "google_maps_embed_url",
            "rating",
            "is_active",
            "amenities",
            "images",
            "room_types",
            "reviews",
            "policies",
            "created_at",
            "updated_at",
        ]


class ReservationSerializer(serializers.ModelSerializer):
    """Serializer for reservation form data from frontend"""
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    room_type_name = serializers.CharField(source='room_type.name', read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id",
            "hotel",
            "hotel_name",
            "room_type",
            "room_type_name",
            "guest_name",
            "guest_email",
            "guest_phone",
            "check_in",
            "check_out",
            "adults",
            "children",
            "rooms_count",
            "total_price",
            "currency",
            "special_requests",
            "status",
            "created_at",
            "whatsapp_message_sent",
        ]
        read_only_fields = ["id", "created_at", "whatsapp_message_sent"]

    def validate(self, attrs):
        check_in = attrs.get("check_in")
        check_out = attrs.get("check_out")
        room_type = attrs.get("room_type")
        rooms_count = attrs.get("rooms_count", 1)

        if check_in and check_out and check_out <= check_in:
            raise serializers.ValidationError("check_out must be after check_in")

        if room_type and attrs.get("hotel") and room_type.hotel_id != attrs["hotel"].id:
            raise serializers.ValidationError("room_type does not belong to this hotel")

        if rooms_count <= 0:
            raise serializers.ValidationError("rooms_count must be >= 1")

        # Calculate total price if not provided
        if check_in and check_out and room_type and not attrs.get("total_price"):
            nights = (check_out - check_in).days
            attrs["total_price"] = room_type.price_per_night * nights * rooms_count

        return attrs


class HotelPartnerRegisterSerializer(serializers.Serializer):
    hotel_name = serializers.CharField(max_length=200)
    place_type = serializers.ChoiceField(
        choices=Hotel.PLACE_TYPE_CHOICES,
        required=False,
        default=Hotel.PLACE_TYPE_HOTEL,
    )
    country = serializers.CharField(max_length=80, allow_blank=True, required=False)
    city = serializers.CharField(max_length=80)
    address = serializers.CharField(max_length=255, allow_blank=True, required=False)
    google_maps_url = serializers.URLField(required=False, allow_blank=True)
    owner_email = serializers.EmailField()

    def validate_google_maps_url(self, value):
        return _normalize_google_maps_url(value)


class HotelClaimSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=200)
    email = serializers.EmailField()


class HotelApprovalSerializer(serializers.ModelSerializer):
    """Minimal serializer for platform owner to view and approve pending hotels."""
    owner_email = serializers.EmailField(source="account.user.email", read_only=True)

    class Meta:
        model = Hotel
        fields = [
            "id",
            "name",
            "country",
            "city",
            "address",
            "is_active",
            "created_at",
            "owner_email",
        ]

