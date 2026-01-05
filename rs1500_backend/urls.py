"""
URL configuration for rs1500_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from accounts.views import (
    GoogleLoginView,
    MeView,
    RequestRegisterView,
    VerifyRegisterOTPView,
    EmailOrUsernameTokenObtainPairView,
)
from hotels.admin import hotel_partner_admin_site

urlpatterns = [
    path('admin/', admin.site.urls),
    path('hotel-admin/', hotel_partner_admin_site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/', EmailOrUsernameTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/me/', MeView.as_view(), name='auth-me'),
    path('api/auth/request-otp/', RequestRegisterView.as_view(), name='request-otp'),
    path('api/auth/verify-otp/', VerifyRegisterOTPView.as_view(), name='verify-otp'),
    path('api/auth/google/', GoogleLoginView.as_view(), name='google-login'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include('hotels.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
