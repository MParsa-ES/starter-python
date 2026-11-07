from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)


class LoginView(TokenObtainPairView):
    throttle_classes = [AnonRateThrottle]


class RefreshView(TokenRefreshView):
    throttle_classes = [AnonRateThrottle]


class LogoutView(TokenBlacklistView):
    throttle_classes = [AnonRateThrottle]
