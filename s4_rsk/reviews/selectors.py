from django.db.models import QuerySet

from .models import ManualReviewItem, ReviewState


def list_review_items(*, state: str | None = None) -> QuerySet[ManualReviewItem]:
    """Return manual review items ordered for cursor pagination, optionally filtered by state."""
    queryset = ManualReviewItem.objects.select_related("claimed_by").all().order_by("-created_at", "-item_id")
    if state is not None:
        queryset = queryset.filter(state=state)
    return queryset


def count_open_items() -> int:
    """Snapshot count of unclaimed OPEN review items for dashboard statistics."""
    return ManualReviewItem.objects.filter(state=ReviewState.OPEN).count()
