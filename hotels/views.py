from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated, IsAuthenticatedOrReadOnly

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
from .serializers import (
    AmenitySerializer,
    BookingSerializer,
    HotelDetailSerializer,
    HotelFacilityMappingSerializer,
    HotelFacilitySerializer,
    HotelImageSerializer,
    HotelImageWriteSerializer,
    HotelPolicySerializer,
    HotelSerializer,
    HotelWriteSerializer,
    ReservationSerializer,
    ReviewSerializer,
    RoomImageSerializer,
    RoomTypeSerializer,
    RoomTypeWithImagesSerializer,
)


class IsAdminOrReadOnly(IsAuthenticatedOrReadOnly):
    def has_permission(self, request, view):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return True
        return bool(getattr(request, "user", None) and request.user.is_staff)


class HotelViewSet(viewsets.ModelViewSet):
    queryset = Hotel.objects.all().order_by("-id")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)

        if user and user.is_staff:
            return (
                qs.select_related()
                .prefetch_related(
                    "amenities",
                    "images",
                    "room_types",
                    "room_types__room_images",
                    "reviews",
                    "facility_mappings__facility",
                )
            )

        return (
            qs.filter(is_active=True)
            .prefetch_related(
                "amenities",
                "images",
                Prefetch(
                    "room_types",
                    queryset=RoomType.objects.filter(is_active=True)
                    .order_by("id")
                    .prefetch_related("room_images"),
                ),
                "reviews",
                "facility_mappings__facility",
            )
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return HotelWriteSerializer
        if self.action == "retrieve":
            return HotelDetailSerializer
        return HotelSerializer


class AmenityViewSet(viewsets.ModelViewSet):
    queryset = Amenity.objects.all().order_by("name")
    serializer_class = AmenitySerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAdminUser()]


class RoomTypeViewSet(viewsets.ModelViewSet):
    queryset = RoomType.objects.select_related("hotel").all().order_by("-id")
    serializer_class = RoomTypeSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        hotel_id = self.request.query_params.get("hotel")
        if hotel_id:
            qs = qs.filter(hotel_id=hotel_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs.prefetch_related("room_images")
        return qs.filter(is_active=True, hotel__is_active=True).prefetch_related("room_images")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RoomTypeWithImagesSerializer
        return RoomTypeSerializer


class HotelImageViewSet(viewsets.ModelViewSet):
    queryset = HotelImage.objects.select_related("hotel").all().order_by("sort_order", "id")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        hotel_id = self.request.query_params.get("hotel")
        if hotel_id:
            qs = qs.filter(hotel_id=hotel_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs
        return qs.filter(hotel__is_active=True)

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return HotelImageWriteSerializer
        return HotelImageSerializer


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.select_related("user", "hotel", "room_type").all().order_by("-id")
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs
        return qs.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RoomImageViewSet(viewsets.ModelViewSet):
    queryset = RoomImage.objects.select_related("room_type", "room_type__hotel").all().order_by("sort_order", "id")
    serializer_class = RoomImageSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        room_type_id = self.request.query_params.get("room_type")
        if room_type_id:
            qs = qs.filter(room_type_id=room_type_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs
        return qs.filter(room_type__is_active=True, room_type__hotel__is_active=True)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related("user", "hotel").all().order_by("-created_at")
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        hotel_id = self.request.query_params.get("hotel")
        if hotel_id:
            qs = qs.filter(hotel_id=hotel_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs
        return qs.filter(hotel__is_active=True)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        obj = self.get_object()
        user = getattr(self.request, "user", None)
        if not (user and (user.is_staff or obj.user_id == user.id)):
            raise PermissionDenied("You can only edit your own review")
        serializer.save()

    def perform_destroy(self, instance):
        user = getattr(self.request, "user", None)
        if not (user and (user.is_staff or instance.user_id == user.id)):
            raise PermissionDenied("You can only delete your own review")
        instance.delete()


class HotelPolicyViewSet(viewsets.ModelViewSet):
    queryset = HotelPolicy.objects.select_related("hotel").all().order_by("-id")
    serializer_class = HotelPolicySerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        hotel_id = self.request.query_params.get("hotel")
        if hotel_id:
            qs = qs.filter(hotel_id=hotel_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs
        return qs.filter(hotel__is_active=True)


class HotelFacilityViewSet(viewsets.ModelViewSet):
    queryset = HotelFacility.objects.all().order_by("name")
    serializer_class = HotelFacilitySerializer
    permission_classes = [IsAdminOrReadOnly]


class HotelFacilityMappingViewSet(viewsets.ModelViewSet):
    queryset = HotelFacilityMapping.objects.select_related("hotel", "facility").all().order_by("-id")
    serializer_class = HotelFacilityMappingSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        hotel_id = self.request.query_params.get("hotel")
        if hotel_id:
            qs = qs.filter(hotel_id=hotel_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs
        return qs.filter(hotel__is_active=True)


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet for handling reservation form data from frontend"""
    queryset = Reservation.objects.select_related("hotel", "room_type").all().order_by("-created_at")
    serializer_class = ReservationSerializer
    permission_classes = [AllowAny]  # Allow anyone to create reservations

    def get_queryset(self):
        qs = super().get_queryset()
        hotel_id = self.request.query_params.get("hotel")
        if hotel_id:
            qs = qs.filter(hotel_id=hotel_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs
        return qs.filter(hotel__is_active=True)
