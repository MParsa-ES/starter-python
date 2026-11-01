from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from common.views import health_view, ready_view

urlpatterns = [
    path("admin/", admin.site.urls),
    # GEN-10: Infrastructure Health & Readiness Probes
    path("health", health_view, name="health"),
    path("ready", ready_view, name="ready"),
    # GEN-01: OpenAPI 3.1 Schema & Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # GEN-02: All Service Endpoints under /api/v1/
    path("api/v1/", include("assessments.urls")),
    path("api/v1/", include("rules.urls")),
    path("api/v1/", include("reviews.urls")),
]
