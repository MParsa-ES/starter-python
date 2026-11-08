from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from common.auth_views import LoginView, LogoutView, RefreshView
from common.views import health_view, ready_view

urlpatterns = [
    path("admin/", admin.site.urls),
    # GEN-10: Infrastructure Health & Readiness Probes
    path("health", health_view, name="health"),
    path("ready", ready_view, name="ready"),
    # GEN-01: OpenAPI 3.1 Schema & Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/token/", LoginView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", RefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/token/logout/", LogoutView.as_view(), name="token_blacklist"),
    # GEN-02: All Service Endpoints under /api/v1/
    path("api/v1/", include("assessments.urls")),
    path("api/v1/", include("rules.urls")),
    path("api/v1/", include("reviews.urls")),
    path("api/v1/", include("dashboard.urls")),
]

# Gunicorn does not serve Django's development static files itself.
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
