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


class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = [
            "id",
            "hotel",
            "name",
            "description",
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
            "description",
            "country",
            "city",
            "address",
            "latitude",
            "longitude",
            "rating",
            "is_active",
            "amenities",
            "images",
            "room_types",
            "created_at",
            "updated_at",
        ]


class HotelWriteSerializer(serializers.ModelSerializer):
    amenities = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Amenity.objects.all(),
        required=False,
    )

    class Meta:
        model = Hotel
        fields = [
            "id",
            "name",
            "description",
            "country",
            "city",
            "address",
            "latitude",
            "longitude",
            "rating",
            "is_active",
            "amenities",
        ]


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
            "description",
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
    facility_mappings = HotelFacilityMappingSerializer(many=True, read_only=True)

    class Meta:
        model = Hotel
        fields = [
            "id",
            "name",
            "description",
            "country",
            "city",
            "address",
            "latitude",
            "longitude",
            "rating",
            "is_active",
            "amenities",
            "images",
            "room_types",
            "reviews",
            "policies",
            "facility_mappings",
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
