from datetime import datetime
from uuid import UUID

from django.db.models import QuerySet
from django.http import Http404

from assessments.models import DecisionEvent


def list_transaction_decision_events(*, transaction_id: UUID) -> QuerySet[DecisionEvent]:
    """Return append-only decision events for one transaction, oldest first, or 404 if none exist"""
    queryset = DecisionEvent.objects.filter(transaction_id=transaction_id).order_by("created_at", "event_id")
    if not queryset.exists():
        raise Http404(f"Decision history for transaction '{transaction_id}' was not found.")
    return queryset


def search_decision_events(
    *,
    decision: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> QuerySet[DecisionEvent]:
    """Bounded search over decision events (newest first) using half-open UTC range [from, to)"""
    queryset = DecisionEvent.objects.all().order_by("-created_at", "-event_id")
    if decision is not None:
        queryset = queryset.filter(decision=decision)
    if from_dt is not None:
        queryset = queryset.filter(created_at__gte=from_dt)
    if to_dt is not None:
        queryset = queryset.filter(created_at__lt=to_dt)
    return queryset
