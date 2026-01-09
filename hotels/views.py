from django.db import transaction
from django.db.models import Prefetch, Q
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.urls import reverse
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAdminUser,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import EmailOTP, HotelAccount
from accounts.serializers import RequestOTPSerializer, VerifyOTPSerializer, UserSerializer
from accounts.utils import create_otp_record, hash_otp

from .models import (
    Amenity,
    Booking,
    Hotel,
    HotelFacility,
    HotelFacilityMapping,
    HotelImage,
    HotelPolicy,
    PartnerRequest,
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
    HotelPartnerRegisterSerializer,
    MediaLibraryItemSerializer,
    HotelClaimSerializer,
    HotelApprovalSerializer,
    PartnerRequestSerializer,
)

import secrets


hotel_approval_signer = TimestampSigner()


def get_user_hotel_id(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    account = getattr(user, "hotel_account", None)
    if not account:
        return None
    return account.hotel_id


def _is_non_empty(value):
    return bool(str(value or "").strip())


def _get_hotel_missing_sections(hotel):
    missing = []

    if not _is_non_empty(getattr(hotel, "name", "")):
        missing.append("Hotel Details")
    if not _is_non_empty(getattr(hotel, "city", "")):
        if "Hotel Details" not in missing:
            missing.append("Hotel Details")
    if not _is_non_empty(getattr(hotel, "address", "")):
        if "Hotel Details" not in missing:
            missing.append("Hotel Details")

    if not getattr(hotel, "images", None) or not hotel.images.exists():
        missing.append("Images")
    if not getattr(hotel, "room_types", None) or not hotel.room_types.exists():
        missing.append("Rooms")
    if not getattr(hotel, "amenities", None) or not hotel.amenities.exists():
        missing.append("Amenities")

    policy = getattr(hotel, "policies", None)
    if not policy:
        missing.append("Policies")
    else:
        if not _is_non_empty(getattr(policy, "cancellation_policy", "")) or not _is_non_empty(
            getattr(policy, "payment_policy", "")
        ):
            missing.append("Policies")

    return missing


def _send_hotel_approval_email(request, hotel):
    owner_email = getattr(settings, "EMAIL_HOST_USER", None)
    if not owner_email:
        return

    # TODO: change this later to the real platform owner email
    owner_email = "ranjitchaudhary057@gmail.com"

    approval_token = hotel_approval_signer.sign(str(hotel.id))
    approval_path = reverse("hotel-partner-approve", kwargs={"token": approval_token})
    approval_url = request.build_absolute_uri(approval_path)

    reject_path = reverse("hotel-partner-reject", kwargs={"token": approval_token})
    reject_url = request.build_absolute_uri(reject_path)

    subject = f"New hotel approval request: {hotel.name}"
    message_lines = [
        "A hotel partner is requesting approval to go live.",
        "",
        f"Hotel name: {hotel.name}",
        f"Country: {hotel.country}",
        f"City: {hotel.city}",
        f"Address: {hotel.address}",
        "",
        "Approve:",
        approval_url,
        "",
        "Reject:",
        reject_url,
    ]

    html_message = f"""
<!doctype html>
<html>
  <body style=\"margin:0;padding:0;background:#f6f7fb;font-family:Arial,Helvetica,sans-serif;\">
    <div style=\"max-width:640px;margin:0 auto;padding:24px;\">
      <div style=\"background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;padding:20px;\">
        <div style=\"font-size:18px;font-weight:700;color:#0f172a;\">Hotel approval request</div>
        <div style=\"margin-top:10px;font-size:14px;line-height:20px;color:#334155;\">
          A hotel partner has completed their listing and is requesting approval.
        </div>

        <div style=\"margin-top:16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:12px;\">
          <div style=\"font-size:14px;font-weight:700;color:#0f172a;\">Hotel</div>
          <div style=\"margin-top:6px;font-size:14px;color:#334155;\"><b>Name:</b> {hotel.name}</div>
          <div style=\"margin-top:4px;font-size:14px;color:#334155;\"><b>Country:</b> {hotel.country}</div>
          <div style=\"margin-top:4px;font-size:14px;color:#334155;\"><b>City:</b> {hotel.city}</div>
          <div style=\"margin-top:4px;font-size:14px;color:#334155;\"><b>Address:</b> {hotel.address}</div>
        </div>

        <div style=\"margin-top:14px;display:flex;gap:12px;flex-wrap:wrap;\">
          <a href=\"{approval_url}\" style=\"display:inline-block;background:#16a34a;color:#ffffff;text-decoration:none;padding:12px 16px;border-radius:10px;font-weight:700;font-size:14px;\">Approve</a>
          <a href=\"{reject_url}\" style=\"display:inline-block;background:#dc2626;color:#ffffff;text-decoration:none;padding:12px 16px;border-radius:10px;font-weight:700;font-size:14px;\">Reject</a>
        </div>

        <div style=\"margin-top:16px;font-size:12px;color:#64748b;\">
          These links expire in 7 days.
        </div>
      </div>
    </div>
  </body>
</html>
"""

    try:
        send_mail(
            subject=subject,
            message="\n".join(message_lines),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[owner_email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        pass


class IsHotelPartner(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and getattr(user, "is_authenticated", False) and hasattr(user, "hotel_account"))


class IsAdminOrHotelPartner(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and (getattr(user, "is_staff", False) or hasattr(user, "hotel_account"))
        )


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if getattr(request, "method", "").upper() in {"GET", "HEAD", "OPTIONS"}:
            return True
        user = getattr(request, "user", None)
        return bool(user and getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False))


class HotelViewSet(viewsets.ModelViewSet):
    queryset = Hotel.objects.all().order_by("-id")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        if self.action == "create":
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user and user.is_staff:
            return super().create(request, *args, **kwargs)

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            if getattr(user, "hotel_account", None):
                raise ValidationError({"detail": "This account already has a hotel."})

            write_serializer = HotelWriteSerializer(
                data=request.data,
                context={"request": request},
            )
            write_serializer.is_valid(raise_exception=True)

            wants_request_approval = bool(write_serializer.validated_data.get("is_active"))
            with transaction.atomic():
                hotel = write_serializer.save(is_active=False)
                HotelAccount.objects.create(user=user, hotel=hotel)

                if wants_request_approval:
                    missing = _get_hotel_missing_sections(hotel)
                    if missing:
                        raise ValidationError(
                            {
                                "detail": "Complete all sections before requesting approval.",
                                "missing": missing,
                            }
                        )
                    if not hotel.approval_requested:
                        hotel.approval_requested = True
                        hotel.save(update_fields=["approval_requested"])
                        _send_hotel_approval_email(request, hotel)

            read_serializer = HotelDetailSerializer(hotel, context={"request": request})
            return Response(read_serializer.data, status=201)

        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            raise PermissionDenied("Linked hotel not found")

        write_serializer = HotelWriteSerializer(
            hotel,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        write_serializer.is_valid(raise_exception=True)

        wants_request_approval = bool(write_serializer.validated_data.get("is_active"))
        with transaction.atomic():
            write_serializer.save(is_active=hotel.is_active)

            if wants_request_approval:
                if hotel.is_active:
                    raise ValidationError(
                        {
                            "detail": "This hotel is already active (approved). No approval request is needed.",
                        }
                    )
                missing = _get_hotel_missing_sections(hotel)
                if missing:
                    raise ValidationError(
                        {
                            "detail": "Complete all sections before requesting approval.",
                            "missing": missing,
                        }
                    )
                if not hotel.approval_requested:
                    hotel.approval_requested = True
                    hotel.save(update_fields=["approval_requested"])
                    _send_hotel_approval_email(request, hotel)

        read_serializer = HotelDetailSerializer(hotel, context={"request": request})
        return Response(read_serializer.data, status=200)

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
                )
            )

        user_hotel_id = get_user_hotel_id(user)
        if self.action in {"update", "partial_update", "destroy"}:
            if not user_hotel_id:
                return qs.none()
            qs = qs.filter(id=user_hotel_id)
            room_types_qs = RoomType.objects.all().order_by("id").prefetch_related("room_images")
        elif user_hotel_id and self.action == "retrieve":
            qs = qs.filter(Q(is_active=True) | Q(id=user_hotel_id))
            room_types_qs = RoomType.objects.all().order_by("id").prefetch_related("room_images")
        else:
            qs = qs.filter(is_active=True)
            room_types_qs = (
                RoomType.objects.filter(is_active=True)
                .order_by("id")
                .prefetch_related("room_images")
            )

        return qs.prefetch_related(
            "amenities",
            "images",
            Prefetch("room_types", queryset=room_types_qs),
            "reviews",
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return HotelWriteSerializer
        if self.action == "retrieve":
            return HotelDetailSerializer
        return HotelSerializer

    def perform_create(self, serializer):
        serializer.save(is_active=False)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def claim(self, request):
        """Allow an authenticated user to claim their hotel and get its data.

        Exposed as POST /api/hotels/claim/ with body:

            {"company_name": "My Hotel Pvt Ltd", "email": "info@myhotel.com"}

        For now, the claim is resolved using the HotelAccount linked to the
        authenticated user (same as /api/hotels/me/). The request body is
        validated but not used for matching, to keep behaviour simple.
        """

        payload_serializer = HotelClaimSerializer(data=request.data)
        payload_serializer.is_valid(raise_exception=True)

        if request.method.lower() == "post":
            return self.create(request)

        user = getattr(request, "user", None)
        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have a hotel linked to this account")

        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            raise PermissionDenied("Linked hotel not found")

        serializer = HotelDetailSerializer(hotel, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["get", "patch", "post"], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Return the Hotel record linked to the authenticated hotel account.

        Used by the frontend partner portal so a hotel user can fetch and edit
        only their own hotel's data.
        """
        if request.method.lower() == "post":
            return self.create(request)

        user = getattr(request, "user", None)
        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have a hotel linked to this account")

        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            raise PermissionDenied("Linked hotel not found")

        if request.method.lower() == "patch":
            write_serializer = HotelWriteSerializer(
                hotel,
                data=request.data,
                partial=True,
                context={"request": request},
            )
            write_serializer.is_valid(raise_exception=True)

            wants_request_approval = bool(write_serializer.validated_data.get("is_active"))
            with transaction.atomic():
                write_serializer.save(is_active=hotel.is_active)

                if wants_request_approval:
                    if hotel.is_active:
                        raise ValidationError(
                            {
                                "detail": "This hotel is already active (approved). No approval request is needed.",
                            }
                        )
                    missing = _get_hotel_missing_sections(hotel)
                    if missing:
                        raise ValidationError(
                            {
                                "detail": "Complete all sections before requesting approval.",
                                "missing": missing,
                            }
                        )
                    if not hotel.approval_requested:
                        hotel.approval_requested = True
                        hotel.save(update_fields=["approval_requested"])
                        _send_hotel_approval_email(request, hotel)

            read_serializer = HotelDetailSerializer(hotel, context={"request": request})
            return Response(read_serializer.data)

        serializer = HotelDetailSerializer(hotel, context={"request": request})
        return Response(serializer.data)

    def perform_update(self, serializer):
        obj = self.get_object()
        user = getattr(self.request, "user", None)

        if user and user.is_staff:
            if "is_active" in serializer.validated_data and serializer.validated_data.get("is_active") != obj.is_active:
                raise ValidationError(
                    {
                        "is_active": "Hotel activation must be done via the admin approval endpoint.",
                    }
                )
            serializer.save(is_active=obj.is_active)
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or hotel_id != obj.id:
            raise PermissionDenied("You do not have permission to modify this hotel")

        wants_request_approval = bool(serializer.validated_data.get("is_active"))

        with transaction.atomic():
            serializer.save(is_active=obj.is_active)

            if wants_request_approval:
                if obj.is_active:
                    raise ValidationError(
                        {
                            "detail": "This hotel is already active (approved). No approval request is needed.",
                        }
                    )
                missing = _get_hotel_missing_sections(obj)
                if missing:
                    raise ValidationError(
                        {
                            "detail": "Complete all sections before requesting approval.",
                            "missing": missing,
                        }
                    )
                if not obj.approval_requested:
                    obj.approval_requested = True
                    obj.save(update_fields=["approval_requested"])
                    _send_hotel_approval_email(self.request, obj)

    def perform_destroy(self, instance):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            instance.delete()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or hotel_id != instance.id:
            raise PermissionDenied("You do not have permission to delete this hotel")

        instance.delete()


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
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        hotel_id = self.request.query_params.get("hotel")
        if hotel_id:
            qs = qs.filter(hotel_id=hotel_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs.prefetch_related("room_images")

        user_hotel_id = get_user_hotel_id(user)
        if user_hotel_id and (not hotel_id or str(hotel_id) == str(user_hotel_id)):
            return qs.filter(hotel_id=user_hotel_id).prefetch_related("room_images")

        return qs.filter(is_active=True, hotel__is_active=True).prefetch_related("room_images")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RoomTypeWithImagesSerializer
        return RoomTypeSerializer

    def create(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user and user.is_staff:
            return super().create(request, *args, **kwargs)

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have permission to create room types")

        data = request.data.copy()
        data.setdefault("hotel", hotel_id)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    def perform_create(self, serializer):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            serializer.save()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have permission to create room types")

        hotel = serializer.validated_data.get("hotel")
        if not hotel or hotel.id != hotel_id:
            raise PermissionDenied("You can only create room types for your own hotel")

        serializer.save()

    def perform_update(self, serializer):
        obj = self.get_object()
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            serializer.save()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or obj.hotel_id != hotel_id:
            raise PermissionDenied("You do not have permission to modify this room type")

        hotel = serializer.validated_data.get("hotel", obj.hotel)
        if hotel.id != hotel_id:
            raise PermissionDenied("You can only assign room types to your own hotel")

        serializer.save()

    def perform_destroy(self, instance):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            instance.delete()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or instance.hotel_id != hotel_id:
            raise PermissionDenied("You do not have permission to delete this room type")

        instance.delete()


class HotelImageViewSet(viewsets.ModelViewSet):
    queryset = HotelImage.objects.select_related("hotel").all().order_by("sort_order", "id")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            hotel_id = self.request.query_params.get("hotel")
            if hotel_id:
                qs = qs.filter(hotel_id=hotel_id)
            return qs

        user_hotel_id = get_user_hotel_id(user)
        if user_hotel_id:
            return qs.filter(hotel_id=user_hotel_id)

        return qs.filter(hotel__is_active=True)

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return HotelImageWriteSerializer
        return HotelImageSerializer

    def get_object(self):
        user = getattr(self.request, "user", None)
        if self.action in {"update", "partial_update", "destroy"} and user and user.is_authenticated:
            queryset = HotelImage.objects.select_related("hotel").all()
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            lookup_value = self.kwargs.get(lookup_url_kwarg)
            return get_object_or_404(queryset, **{self.lookup_field: lookup_value})
        return super().get_object()

    def create(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user and user.is_staff:
            return super().create(request, *args, **kwargs)

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have permission to create hotel images")

        data = request.data.copy()
        data.setdefault("hotel", hotel_id)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    def perform_create(self, serializer):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            serializer.save()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have permission to create hotel images")

        hotel = serializer.validated_data.get("hotel")
        if not hotel or hotel.id != hotel_id:
            raise PermissionDenied("You can only add images for your own hotel")

        instance = serializer.save()
        if getattr(instance, "is_cover", False):
            HotelImage.objects.filter(hotel_id=instance.hotel_id).exclude(id=instance.id).update(is_cover=False)

    def perform_update(self, serializer):
        obj = self.get_object()
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            instance = serializer.save()
            if getattr(instance, "is_cover", False):
                HotelImage.objects.filter(hotel_id=instance.hotel_id).exclude(id=instance.id).update(is_cover=False)
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or obj.hotel_id != hotel_id:
            raise PermissionDenied("You do not have permission to modify this hotel image")

        hotel = serializer.validated_data.get("hotel", obj.hotel)
        if hotel.id != hotel_id:
            raise PermissionDenied("You can only assign images to your own hotel")

        instance = serializer.save()
        if getattr(instance, "is_cover", False):
            HotelImage.objects.filter(hotel_id=instance.hotel_id).exclude(id=instance.id).update(is_cover=False)

    @action(detail=False, methods=["post"], url_path="bulk-delete", permission_classes=[IsAuthenticated])
    def bulk_delete(self, request):
        user = getattr(request, "user", None)
        ids = request.data.get("ids")

        if not isinstance(ids, list) or not ids:
            return Response({"detail": "'ids' must be a non-empty list."}, status=400)

        qs = HotelImage.objects.filter(id__in=ids)

        if not (user and user.is_staff):
            hotel_id = get_user_hotel_id(user)
            if not hotel_id:
                raise PermissionDenied("You do not have permission to delete hotel images")
            qs = qs.filter(hotel_id=hotel_id)

        deleted_count = qs.count()
        qs.delete()

        return Response({"deleted": deleted_count}, status=200)

    def perform_destroy(self, instance):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            instance.delete()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or instance.hotel_id != hotel_id:
            raise PermissionDenied("You do not have permission to delete this hotel image")

        instance.delete()


class MediaLibraryViewSet(viewsets.ViewSet):
    """Media library for hotel partners using HotelImage records.

    GET /api/media-library/ -> list images for the partner's hotel
    POST /api/media-library/upload/ -> upload an image file and create a HotelImage
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = getattr(request, "user", None)
        hotel_id = get_user_hotel_id(user)

        qs = HotelImage.objects.all().order_by("sort_order", "id")

        if user and user.is_staff:
            hotel_param = request.query_params.get("hotel")
            if hotel_param:
                qs = qs.filter(hotel_id=hotel_param)
        else:
            if not hotel_id:
                return Response([], status=200)
            qs = qs.filter(hotel_id=hotel_id)

        serializer = MediaLibraryItemSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="upload", permission_classes=[IsAuthenticated])
    def upload(self, request):
        user = getattr(request, "user", None)
        file_obj = request.FILES.get("file")

        if not file_obj:
            return Response({"detail": "No file uploaded."}, status=400)

        hotel_id = get_user_hotel_id(user)

        # Allow only hotel partners by default; staff can optionally target a hotel via request data
        target_hotel_id = None
        if user and user.is_staff:
            target_hotel_id = request.data.get("hotel") or hotel_id
        else:
            target_hotel_id = hotel_id

        if not target_hotel_id:
            raise PermissionDenied("You do not have a hotel linked to this account")

        try:
            hotel = Hotel.objects.get(pk=target_hotel_id)
        except Hotel.DoesNotExist:
            raise PermissionDenied("Invalid hotel for media upload")

        # Save the uploaded file under MEDIA_ROOT and build a public URL
        saved_path = default_storage.save(f"hotel_media/{hotel.id}/{file_obj.name}", file_obj)
        relative_url = default_storage.url(saved_path)
        absolute_url = request.build_absolute_uri(relative_url)

        image = HotelImage.objects.create(hotel=hotel, image_url=absolute_url)

        return Response({"id": image.id, "image_url": image.image_url}, status=201)

    @action(detail=False, methods=["post"], url_path="delete", permission_classes=[IsAuthenticated])
    def delete(self, request):
        user = getattr(request, "user", None)
        image_id = request.data.get("id")

        if not image_id:
            return Response({"detail": "'id' is required."}, status=400)

        qs = HotelImage.objects.filter(id=image_id)

        if not (user and user.is_staff):
            hotel_id = get_user_hotel_id(user)
            if not hotel_id:
                raise PermissionDenied("You do not have permission to delete hotel images")
            qs = qs.filter(hotel_id=hotel_id)

        deleted, _ = qs.delete()
        if deleted == 0:
            return Response({"detail": "Hotel image not found."}, status=404)

        return Response({"deleted": deleted}, status=200)

    @action(detail=False, methods=["post"], url_path="bulk-delete", permission_classes=[IsAuthenticated])
    def bulk_delete(self, request):
        user = getattr(request, "user", None)
        ids = request.data.get("ids")

        if not isinstance(ids, list) or not ids:
            return Response({"detail": "'ids' must be a non-empty list."}, status=400)

        qs = HotelImage.objects.filter(id__in=ids)

        if not (user and user.is_staff):
            hotel_id = get_user_hotel_id(user)
            if not hotel_id:
                raise PermissionDenied("You do not have permission to delete hotel images")
            qs = qs.filter(hotel_id=hotel_id)

        deleted_count = qs.count()
        qs.delete()

        return Response({"deleted": deleted_count}, status=200)


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.select_related("user", "hotel", "room_type").all().order_by("-id")
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs
        hotel_id = get_user_hotel_id(user)
        if hotel_id:
            return qs.filter(hotel_id=hotel_id)
        return qs.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RoomImageViewSet(viewsets.ModelViewSet):
    queryset = RoomImage.objects.select_related("room_type", "room_type__hotel").all().order_by("sort_order", "id")
    serializer_class = RoomImageSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        room_type_id = self.request.query_params.get("room_type")
        if room_type_id:
            qs = qs.filter(room_type_id=room_type_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs

        user_hotel_id = get_user_hotel_id(user)
        if user_hotel_id:
            return qs.filter(room_type__hotel_id=user_hotel_id)

        return qs.filter(room_type__is_active=True, room_type__hotel__is_active=True)

    def perform_create(self, serializer):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            serializer.save()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have permission to create room images")

        room_type = serializer.validated_data.get("room_type")
        if not room_type or room_type.hotel_id != hotel_id:
            raise PermissionDenied("You can only add images for your own hotel's room types")

        serializer.save()

    def perform_update(self, serializer):
        obj = self.get_object()
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            serializer.save()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or obj.room_type.hotel_id != hotel_id:
            raise PermissionDenied("You do not have permission to modify this room image")

        room_type = serializer.validated_data.get("room_type", obj.room_type)
        if room_type.hotel_id != hotel_id:
            raise PermissionDenied("You can only assign images to your own hotel's room types")

        serializer.save()

    def perform_destroy(self, instance):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            instance.delete()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or instance.room_type.hotel_id != hotel_id:
            raise PermissionDenied("You do not have permission to delete this room image")

        instance.delete()


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

        user_hotel_id = get_user_hotel_id(user)
        if user_hotel_id and (not hotel_id or str(hotel_id) == str(user_hotel_id)):
            return qs.filter(hotel_id=user_hotel_id)

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
    permission_classes = [IsAuthenticatedOrReadOnly]

    def create(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user and user.is_staff:
            return super().create(request, *args, **kwargs)

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have permission to create hotel policies")

        try:
            existing = HotelPolicy.objects.get(hotel_id=hotel_id)
        except HotelPolicy.DoesNotExist:
            existing = None

        data = request.data.copy()
        data.setdefault("hotel", hotel_id)

        serializer = self.get_serializer(
            instance=existing,
            data=data,
            partial=bool(existing),
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer) if existing is None else self.perform_update(serializer)
        return Response(serializer.data, status=200 if existing else 201)

    def get_queryset(self):
        qs = super().get_queryset()
        hotel_id = self.request.query_params.get("hotel")
        if hotel_id:
            qs = qs.filter(hotel_id=hotel_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs

        user_hotel_id = get_user_hotel_id(user)
        if user_hotel_id and (not hotel_id or str(hotel_id) == str(user_hotel_id)):
            return qs.filter(hotel_id=user_hotel_id)

        return qs.filter(hotel__is_active=True)

    def perform_create(self, serializer):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            serializer.save()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have permission to create hotel policies")

        hotel = serializer.validated_data.get("hotel")
        if not hotel or hotel.id != hotel_id:
            raise PermissionDenied("You can only create policies for your own hotel")

        serializer.save()

    def perform_update(self, serializer):
        obj = self.get_object()
        user = getattr(self.request, "user", None)

        if user and user.is_staff:
            serializer.save()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or obj.hotel_id != hotel_id:
            raise PermissionDenied("You do not have permission to modify this hotel policy")

        hotel = serializer.validated_data.get("hotel", obj.hotel)
        if hotel.id != hotel_id:
            raise PermissionDenied("You can only assign policies to your own hotel")

        serializer.save()

    def perform_destroy(self, instance):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            instance.delete()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or instance.hotel_id != hotel_id:
            raise PermissionDenied("You do not have permission to delete this hotel policy")

        instance.delete()


class PartnerRequestViewSet(viewsets.ModelViewSet):
    queryset = PartnerRequest.objects.all().order_by("-created_at")
    serializer_class = PartnerRequestSerializer

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsAdminUser()]


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
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        hotel_id = self.request.query_params.get("hotel")
        if hotel_id:
            qs = qs.filter(hotel_id=hotel_id)
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return qs

        user_hotel_id = get_user_hotel_id(user)
        if user_hotel_id and (not hotel_id or str(hotel_id) == str(user_hotel_id)):
            return qs.filter(hotel_id=user_hotel_id)

        return qs.filter(hotel__is_active=True)

    def create(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user and user.is_staff:
            return super().create(request, *args, **kwargs)

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have permission to create facility mappings")

        data = request.data.copy()
        data.setdefault("hotel", hotel_id)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    def perform_create(self, serializer):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            serializer.save()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have permission to create facility mappings")

        hotel = serializer.validated_data.get("hotel")
        if not hotel or hotel.id != hotel_id:
            raise PermissionDenied("You can only create facility mappings for your own hotel")

        serializer.save()

    def perform_update(self, serializer):
        obj = self.get_object()
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            serializer.save()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or obj.hotel_id != hotel_id:
            raise PermissionDenied("You do not have permission to modify this facility mapping")

        hotel = serializer.validated_data.get("hotel", obj.hotel)
        if hotel.id != hotel_id:
            raise PermissionDenied("You can only assign facility mappings to your own hotel")

        serializer.save()

    def perform_destroy(self, instance):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            instance.delete()
            return

        hotel_id = get_user_hotel_id(user)
        if not hotel_id or instance.hotel_id != hotel_id:
            raise PermissionDenied("You do not have permission to delete this facility mapping")

        instance.delete()


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet for handling reservation form data from frontend"""
    queryset = Reservation.objects.select_related("hotel", "room_type").all().order_by("-created_at")
    serializer_class = ReservationSerializer
    permission_classes = [AllowAny]  # Allow anyone to create reservations

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        hotel_param = self.request.query_params.get("hotel")

        if user and user.is_staff:
            if hotel_param:
                qs = qs.filter(hotel_id=hotel_param)

            return qs

        user_hotel_id = get_user_hotel_id(user)
        if user_hotel_id:
            return qs.filter(hotel_id=user_hotel_id)

        if hotel_param:
            qs = qs.filter(hotel_id=hotel_param)

        return qs.filter(hotel__is_active=True)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def my(self, request):
        """Return reservations associated with the authenticated user's email.

        Used by the public Next.js profile page so a logged-in guest can see
        their own reservation requests and statuses (pending/confirmed/cancelled).
        """
        user = getattr(request, "user", None)
        email = getattr(user, "email", None)

        if not email:
            return Response([], status=200)

        base_qs = self.get_queryset()
        qs = base_qs.filter(guest_email=email)
        qs = self.filter_queryset(qs)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class HotelPartnerRegisterView(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        serializer = HotelPartnerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email = data["owner_email"].lower()

        user = User.objects.filter(email__iexact=email).first()
        if user and hasattr(user, "hotel_account"):
            return Response({"detail": "A hotel account already exists for this email."}, status=400)

        if not user:
            base_username = email.split("@")[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=email,
                password=None,
                is_active=True,
            )

        hotel = Hotel.objects.create(
            name=data["hotel_name"],
            place_type=data.get("place_type") or Hotel.PLACE_TYPE_HOTEL,
            country=data.get("country") or "",
            city=data["city"],
            address=data.get("address") or "",
            google_maps_url=data.get("google_maps_url") or "",
            # New partner hotels start as inactive until the platform owner approves.
            is_active=False,
        )

        HotelAccount.objects.create(user=user, hotel=hotel)

        # NOTE: Registration only creates a draft hotel. Approval is requested later
        # once the partner completes all hotel details inside the hotel admin portal.

        login(request, user)
        refresh = RefreshToken.for_user(user)
        name = (f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}").strip()
        if not name:
            name = (getattr(user, "username", "") or "").strip()
        if not name:
            name = (getattr(user, "email", "") or "").strip()

        return Response(
            {
                "detail": "Hotel partner registered and logged in.",
                "hotel_id": hotel.id,
                "redirect_url": "/hotel-admin/",
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
                "email": getattr(user, "email", None),
                "name": name,
                "role": "partner",
            },
            status=201,
        )


class HotelPartnerRequestOTPView(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()

        user = User.objects.filter(email__iexact=email, hotel_account__isnull=False).first()
        if not user:
            return Response({"detail": "No hotel account found for this email."}, status=400)

        otp, _ = create_otp_record(email, expiry_minutes=2)

        try:
            send_mail(
                subject="Your hotel admin login OTP",
                message=f"Your OTP code is: {otp}\nIt expires in 2 minutes.",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            return Response({"detail": f"Failed to send email: {str(e)}"}, status=500)

        return Response({"detail": "OTP sent to email."}, status=200)


class HotelPartnerVerifyOTPView(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        otp = serializer.validated_data["otp"]

        record = EmailOTP.objects.filter(email__iexact=email).order_by("-created_at").first()
        user = User.objects.filter(email__iexact=email, hotel_account__isnull=False).first()

        if not user:
            return Response({"detail": "Invalid email or OTP."}, status=400)

        if not record or record.used or record.is_expired() or record.attempts >= 5:
            return Response({"detail": "Invalid or expired OTP."}, status=400)

        candidate_hash = hash_otp(otp, record.salt)
        if secrets.compare_digest(candidate_hash, record.otp_hash):
            record.used = True
            record.save()

            login(request, user)
            refresh = RefreshToken.for_user(user)
            name = (f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}").strip()
            if not name:
                name = (getattr(user, "username", "") or "").strip()
            if not name:
                name = (getattr(user, "email", "") or "").strip()

            return Response(
                {
                    "detail": "OTP verified. Logged into hotel admin.",
                    "hotel_id": getattr(getattr(user, "hotel_account", None), "hotel_id", None),
                    "redirect_url": "/hotel-admin/",
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": UserSerializer(user).data,
                    "email": getattr(user, "email", None),
                    "name": name,
                    "role": "partner",
                },
                status=200,
            )

        record.attempts += 1
        record.save()
        return Response({"detail": "Invalid OTP."}, status=400)


def hotel_partner_approve_view(request, token):
    """Approve a hotel partner registration via a signed one-click link.

    The link is sent to platform owner by email and contains a signed token
    for the hotel ID. When opened, the hotel is marked as active so it becomes
    visible on the public frontend.
    """

    if not (getattr(request.user, "is_authenticated", False) and request.user.is_staff):
        return HttpResponse("Access denied: admin only.", status=403)

    try:
        hotel_id = hotel_approval_signer.unsign(token, max_age=7 * 24 * 60 * 60)
    except SignatureExpired:
        return HttpResponse("Approval link has expired.", status=400)
    except BadSignature:
        return HttpResponse("Invalid approval link.", status=400)

    try:
        hotel = Hotel.objects.get(pk=hotel_id)
    except Hotel.DoesNotExist:
        return HttpResponse("Hotel not found.", status=404)

    if not getattr(hotel, "approval_requested", False):
        return HttpResponse(
            "This hotel has not requested approval yet.",
            status=400,
        )

    if hotel.is_active:
        return HttpResponse(
            "Hotel is already approved and visible on the platform.", status=200
        )

    hotel.is_active = True
    hotel.save(update_fields=["is_active"])

    return HttpResponse(
        "Hotel has been approved and is now visible on the platform.", status=200
    )


def hotel_partner_reject_view(request, token):
    """Reject a hotel approval request via a signed one-click link."""

    if not (getattr(request.user, "is_authenticated", False) and request.user.is_staff):
        return HttpResponse("Access denied: admin only.", status=403)

    try:
        hotel_id = hotel_approval_signer.unsign(token, max_age=7 * 24 * 60 * 60)
    except SignatureExpired:
        return HttpResponse("Rejection link has expired.", status=400)
    except BadSignature:
        return HttpResponse("Invalid rejection link.", status=400)

    try:
        hotel = Hotel.objects.get(pk=hotel_id)
    except Hotel.DoesNotExist:
        return HttpResponse("Hotel not found.", status=404)

    if not getattr(hotel, "approval_requested", False):
        return HttpResponse(
            "This hotel has not requested approval yet.",
            status=400,
        )

    if hotel.is_active:
        return HttpResponse(
            "Hotel is already approved and visible on the platform.", status=200
        )

    hotel.approval_requested = False
    hotel.save(update_fields=["approval_requested"])

    return HttpResponse(
        "Hotel approval request has been rejected.",
        status=200,
    )


class HotelPartnerApprovalListView(viewsets.ReadOnlyModelViewSet):
    queryset = Hotel.objects.select_related("account__user").all().order_by("-created_at")
    serializer_class = HotelApprovalSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(is_active=False, approval_requested=True)


class AdminHotelApprovalPage(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = (JWTAuthentication, SessionAuthentication)
    renderer_classes = [TemplateHTMLRenderer, JSONRenderer]
    template_name = "hotels/admin_approve.html"

    def get_permissions(self):
        if getattr(self.request, "method", "").upper() == "POST":
            return [IsAuthenticated(), IsAdminOrHotelPartner()]
        return [IsAdminUser()]

    def get(self, request):
        pending_qs = (
            Hotel.objects.select_related("account__user")
            .filter(is_active=False, approval_requested=True)
            .order_by("-created_at")
        )

        if getattr(getattr(request, "accepted_renderer", None), "format", None) == "json":
            serializer = HotelApprovalSerializer(pending_qs, many=True)
            return Response(serializer.data)

        pending_hotels = []
        for hotel in pending_qs:
            token = hotel_approval_signer.sign(str(hotel.id))
            approve_path = reverse("hotel-partner-approve", kwargs={"token": token})
            reject_path = reverse("hotel-partner-reject", kwargs={"token": token})

            owner_email = None
            account = getattr(hotel, "account", None)
            if account and getattr(account, "user", None):
                owner_email = getattr(account.user, "email", None)

            pending_hotels.append(
                {
                    "id": hotel.id,
                    "name": hotel.name,
                    "country": hotel.country,
                    "city": hotel.city,
                    "owner_email": owner_email or "",
                    "approve_url": request.build_absolute_uri(approve_path),
                    "reject_url": request.build_absolute_uri(reject_path),
                }
            )

        context = {"pending_hotels": pending_hotels}
        return Response(context)

    def post(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_staff", False):
            hotel_id = request.data.get("hotel_id")
            action = (request.data.get("action") or "").strip().lower()

            if not hotel_id:
                raise ValidationError({"hotel_id": "This field is required."})
            if action not in {"approve", "reject"}:
                raise ValidationError({"action": "Invalid action. Use 'approve' or 'reject'."})

            try:
                hotel_id_int = int(hotel_id)
            except (TypeError, ValueError):
                raise ValidationError({"hotel_id": "A valid integer is required."})

            try:
                hotel = Hotel.objects.get(pk=hotel_id_int)
            except Hotel.DoesNotExist:
                return Response({"detail": "Hotel not found."}, status=404)

            if action == "approve":
                if not getattr(hotel, "approval_requested", False):
                    raise ValidationError({"detail": "This hotel has not requested approval yet."})
                if hotel.is_active:
                    raise ValidationError({"detail": "Hotel is already approved and visible on the platform."})

                hotel.is_active = True
                hotel.save(update_fields=["is_active"])
                return Response({"detail": "Hotel has been approved and is now visible on the platform."}, status=200)

            if not getattr(hotel, "approval_requested", False):
                raise ValidationError({"detail": "This hotel has not requested approval yet."})
            if hotel.is_active:
                raise ValidationError({"detail": "Hotel is already approved and visible on the platform."})

            hotel.approval_requested = False
            hotel.save(update_fields=["approval_requested"])
            return Response({"detail": "Hotel approval request has been rejected."}, status=200)

        hotel_id = get_user_hotel_id(user)
        if not hotel_id:
            raise PermissionDenied("You do not have permission to request hotel approval")

        try:
            hotel = Hotel.objects.get(pk=hotel_id)
        except Hotel.DoesNotExist:
            return Response({"detail": "Hotel not found."}, status=404)

        if hotel.is_active:
            raise ValidationError(
                {"detail": "This hotel is already active (approved). No approval request is needed."}
            )

        missing = _get_hotel_missing_sections(hotel)
        if missing:
            raise ValidationError(
                {
                    "detail": "Complete all sections before requesting approval.",
                    "missing": missing,
                }
            )

        if not getattr(hotel, "approval_requested", False):
            hotel.approval_requested = True
            hotel.save(update_fields=["approval_requested"])
            _send_hotel_approval_email(request, hotel)

        return Response({"detail": "Approval request submitted."}, status=200)


def hotel_partner_admin_approval_page(request):
    """Render an HTML page for platform owner to approve/reject pending hotels."""
    if not (getattr(request.user, "is_authenticated", False) and request.user.is_staff):
        return HttpResponse("Access denied: admin only.", status=403)

    pending_qs = (
        Hotel.objects.select_related("account__user")
        .filter(is_active=False, approval_requested=True)
        .order_by("-created_at")
    )

    pending_hotels = []
    for hotel in pending_qs:
        token = hotel_approval_signer.sign(str(hotel.id))
        approve_path = reverse("hotel-partner-approve", kwargs={"token": token})
        reject_path = reverse("hotel-partner-reject", kwargs={"token": token})

        owner_email = None
        account = getattr(hotel, "account", None)
        if account and getattr(account, "user", None):
            owner_email = getattr(account.user, "email", None)

        pending_hotels.append(
            {
                "id": hotel.id,
                "name": hotel.name,
                "country": hotel.country,
                "city": hotel.city,
                "owner_email": owner_email or "",
                "approve_url": request.build_absolute_uri(approve_path),
                "reject_url": request.build_absolute_uri(reject_path),
            }
        )

    context = {"pending_hotels": pending_hotels}
    return render(request, "hotels/admin_approve.html", context)
