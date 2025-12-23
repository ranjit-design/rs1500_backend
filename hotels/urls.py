from rest_framework.routers import DefaultRouter

from .views import (
    AmenityViewSet,
    BookingViewSet,
    HotelFacilityMappingViewSet,
    HotelFacilityViewSet,
    HotelImageViewSet,
    HotelPolicyViewSet,
    HotelViewSet,
    ReservationViewSet,
    ReviewViewSet,
    RoomImageViewSet,
    RoomTypeViewSet,
)

router = DefaultRouter()
router.register(r"hotels", HotelViewSet, basename="hotel")
router.register(r"amenities", AmenityViewSet, basename="amenity")
router.register(r"room-types", RoomTypeViewSet, basename="roomtype")
router.register(r"hotel-images", HotelImageViewSet, basename="hotelimage")
router.register(r"room-images", RoomImageViewSet, basename="roomimage")
router.register(r"bookings", BookingViewSet, basename="booking")
router.register(r"reservations", ReservationViewSet, basename="reservation")
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"hotel-policies", HotelPolicyViewSet, basename="hotelpolicy")
router.register(r"facilities", HotelFacilityViewSet, basename="facility")
router.register(r"facility-mappings", HotelFacilityMappingViewSet, basename="facilitymapping")

urlpatterns = router.urls
