from django.db.models import QuerySet

from .models import BlockedIdentifier


def list_blocked_identifiers(*, active: bool | None = None) -> QuerySet[BlockedIdentifier]:
    """Return blocked identifiers ordered for cursor pagination, optionally filtered by active flag"""
    queryset = BlockedIdentifier.objects.select_related("created_by").all().order_by("-created_at", "-id")
    if active is not None:
        queryset = queryset.filter(active=active)
    return queryset
