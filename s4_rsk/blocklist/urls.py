from django.urls import path

from .views import BlockedIdentifierDetailView, BlockedIdentifierListCreateView

urlpatterns = [
    path("blocked-identifiers", BlockedIdentifierListCreateView.as_view(), name="blocked-identifier-list"),
    path(
        "blocked-identifiers/<uuid:identifier_id>",
        BlockedIdentifierDetailView.as_view(),
        name="blocked-identifier-detail",
    ),
]
