from django.urls import path
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
    HotelPartnerRegisterView,
    HotelPartnerRequestOTPView,
    HotelPartnerVerifyOTPView,
    MediaLibraryViewSet,
    hotel_partner_approve_view,
    hotel_partner_reject_view,
    HotelPartnerApprovalListView,
    hotel_partner_admin_approval_page,
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
router.register(r"media-library", MediaLibraryViewSet, basename="medialibrary")
router.register(r"hotel-partner-approvals", HotelPartnerApprovalListView, basename="hotel-partner-approval")

urlpatterns = router.urls + [
    path(
        "hotel-partner/register/",
        HotelPartnerRegisterView.as_view({"post": "create"}),
        name="hotel-partner-register",
    ),
    path(
        "hotel-partner/request-otp/",
        HotelPartnerRequestOTPView.as_view({"post": "create"}),
        name="hotel-partner-request-otp",
    ),
    path(
        "hotel-partner/verify-otp/",
        HotelPartnerVerifyOTPView.as_view({"post": "create"}),
        name="hotel-partner-verify-otp",
    ),
    path(
        "hotel-partner/approve/<str:token>/",
        hotel_partner_approve_view,
        name="hotel-partner-approve",
    ),
    path(
        "hotel-partner/reject/<str:token>/",
        hotel_partner_reject_view,
        name="hotel-partner-reject",
    ),
    path(
        "admin/approve-hotels/",
        hotel_partner_admin_approval_page,
        name="hotel-admin-approve-page",
    ),
]
