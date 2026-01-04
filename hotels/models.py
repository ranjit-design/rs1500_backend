from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Amenity(models.Model):
    name = models.CharField(max_length=80, unique=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Font Awesome icon class (e.g., 'fa-wifi', 'fa-swimming-pool')"
    )

    def __str__(self):
        return self.name


class Hotel(models.Model):
    PLACE_TYPE_HOTEL = "hotel"
    PLACE_TYPE_RESORT = "resort"
    PLACE_TYPE_LODGE = "lodge"
    PLACE_TYPE_APARTMENT = "apartment"
    PLACE_TYPE_GUEST_HOUSE = "guest_house"
    PLACE_TYPE_HOME_STAY = "home_stay"
    PLACE_TYPE_CAMPSITE = "campsite"
    PLACE_TYPE_VILLA = "villa"

    PLACE_TYPE_CHOICES = [
        (PLACE_TYPE_HOTEL, "Hotel"),
        (PLACE_TYPE_RESORT, "Resort"),
        (PLACE_TYPE_LODGE, "Lodge"),
        (PLACE_TYPE_APARTMENT, "Apartment"),
        (PLACE_TYPE_GUEST_HOUSE, "Guest House"),
        (PLACE_TYPE_HOME_STAY, "Home Stay"),
        (PLACE_TYPE_CAMPSITE, "Campsite"),
        (PLACE_TYPE_VILLA, "Villa"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    country = models.CharField(max_length=80, blank=True)
    city = models.CharField(max_length=80, db_index=True)
    address = models.CharField(max_length=255, blank=True)

    google_maps_url = models.URLField(max_length=500, blank=True)

    place_type = models.CharField(
        max_length=20,
        choices=PLACE_TYPE_CHOICES,
        default=PLACE_TYPE_HOTEL,
    )

    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    approval_requested = models.BooleanField(default=False)

    amenities = models.ManyToManyField(Amenity, blank=True, related_name="hotels")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class HotelImage(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="images")
    image_url = models.URLField(max_length=500)
    is_cover = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.hotel_id} - {self.image_url}"


class RoomType(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="room_types")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    max_adults = models.PositiveSmallIntegerField(default=2)
    max_children = models.PositiveSmallIntegerField(default=0)
    max_guests = models.PositiveSmallIntegerField(default=2)

    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="NPR")

    total_rooms = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("hotel", "name")

    def __str__(self):
        return f"{self.hotel_id} - {self.name}"


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="bookings")
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name="bookings")

    check_in = models.DateField()
    check_out = models.DateField()

    adults = models.PositiveSmallIntegerField(default=2)
    children = models.PositiveSmallIntegerField(default=0)
    rooms_count = models.PositiveSmallIntegerField(default=1)

    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_id} - {self.hotel_id} - {self.status}"


class Review(models.Model):
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]
    
    hotel = models.ForeignKey(
        Hotel, 
        on_delete=models.CASCADE, 
        related_name='reviews'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hotel_reviews'
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('hotel', 'user')
    
    def __str__(self):
        return f"{self.user.email}'s {self.rating}-star review for {self.hotel.name}"


class HotelPolicy(models.Model):
    hotel = models.OneToOneField(
        Hotel,
        on_delete=models.CASCADE,
        related_name='policies'
    )
    check_in_time = models.TimeField(default='14:00')
    check_out_time = models.TimeField(default='12:00')
    cancellation_policy = models.TextField(help_text="Cancellation policy details")
    payment_policy = models.TextField(help_text="Payment and deposit policy")
    child_policy = models.TextField(blank=True, help_text="Policies regarding children")
    pet_policy = models.TextField(blank=True, help_text="Policies regarding pets")
    additional_info = models.TextField(blank=True, help_text="Any additional policies")
    
    def __str__(self):
        return f"Policies for {self.hotel.name}"


class RoomImage(models.Model):
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.CASCADE,
        related_name='room_images'
    )
    image_url = models.URLField(max_length=500)
    is_primary = models.BooleanField(default=False)
    caption = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'id']
    
    def __str__(self):
        return f"{self.room_type.hotel.name} - {self.room_type.name} Image"


class HotelFacility(models.Model):
    CATEGORY_CHOICES = [
        ('general', 'General Facilities'),
        ('food', 'Food & Drink'),
        ('wellness', 'Wellness & Spa'),
        ('business', 'Business Facilities'),
        ('transport', 'Transportation'),
        ('safety', 'Safety & Security'),
    ]
    
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    icon_class = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="Font Awesome or other icon class"
    )
    
    def __str__(self):
        return self.name


class HotelFacilityMapping(models.Model):
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='facility_mappings'
    )
    facility = models.ForeignKey(
        HotelFacility,
        on_delete=models.CASCADE,
        related_name='hotel_mappings'
    )
    description = models.TextField(blank=True)
    is_available = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('hotel', 'facility')
    
    def __str__(self):
        return f"{self.hotel.name} - {self.facility.name}"


class Reservation(models.Model):
    """Model to store reservation form data from frontend"""
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="reservations")
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name="reservations")
    
    # Guest information
    guest_name = models.CharField(max_length=100)
    guest_email = models.EmailField()
    guest_phone = models.CharField(max_length=20)
    
    # Booking details
    check_in = models.DateField()
    check_out = models.DateField()
    adults = models.PositiveSmallIntegerField(default=2)
    children = models.PositiveSmallIntegerField(default=0)
    rooms_count = models.PositiveSmallIntegerField(default=1)
    
    # Pricing
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="NPR")
    
    # Additional information from form
    special_requests = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    whatsapp_message_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.guest_name} - {self.hotel.name} - {self.check_in} to {self.check_out}"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Reservation status: pending, confirmed, or cancelled.",
    )
