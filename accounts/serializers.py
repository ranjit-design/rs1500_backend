from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','email']


class RequestOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.RegexField(regex=r"^\d{6}$")


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Allow JWT login using either username or email.

    The client should continue to POST a field named "username" together with
    "password". This serializer will detect when the value in "username" looks
    like an email address and, if so, resolve it to the actual username linked
    to that email before delegating to the default SimpleJWT behaviour.
    """

    def validate(self, attrs):
        username = attrs.get(self.username_field)

        # If the provided username string looks like an email, try to map it to
        # the real username for that user. If no user is found, we simply fall
        # back to the base class behaviour so the error message stays
        # consistent ("no_active_account").
        if username and "@" in username:
            try:
                user = User.objects.get(email__iexact=username)
            except User.DoesNotExist:
                pass
            else:
                attrs[self.username_field] = user.get_username()

        return super().validate(attrs)