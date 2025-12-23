# accounts/utils.py
import secrets, hashlib
from datetime import timedelta
from django.utils import timezone

def generate_numeric_otp(length=6):
    # returns string e.g. "483920"
    min_val = 10**(length-1)
    max_val = 10**length - 1
    return str(secrets.randbelow(max_val - min_val + 1) + min_val)

def hash_otp(otp, salt):
    return hashlib.sha256((salt + otp).encode()).hexdigest()

def create_otp_record(email, expiry_minutes=10):
    from .models import EmailOTP
    otp = generate_numeric_otp()
    salt = secrets.token_hex(8)
    otp_hash = hash_otp(otp, salt)
    expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
    # create or update — overwrite previous OTP for same email
    record, created = EmailOTP.objects.update_or_create(
        email=email,
        defaults={"otp_hash": otp_hash, "salt": salt, "expires_at": expires_at, "attempts": 0, "used": False}
    )
    return otp, record
