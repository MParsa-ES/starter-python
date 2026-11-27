from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from rest_framework import status

from assessments.models import DecisionEvent, DecisionType, EventType, RiskAssessment
from common.exceptions import LabBankAPIException
from common.middleware import get_correlation_id

from .models import ManualReviewItem, ReviewState


def _check_operator(actor) -> None:
    if (
        not actor
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.groups.filter(name="operator").exists()
    ):
        raise PermissionDenied("An active operator is required.")


def enqueue_review_item(*, assessment: RiskAssessment) -> ManualReviewItem:
    """Create an OPEN manual review queue item for a REVIEW assessment."""
    return ManualReviewItem.objects.create(
        assessment=assessment,
        transaction_id=assessment.transaction_id,
        state=ReviewState.OPEN,
    )


@transaction.atomic
def claim_review_item(*, actor, item_id: UUID) -> ManualReviewItem:
    """Atomically claim an OPEN review item; rejects already claimed or decided items with 409."""
    _check_operator(actor)

    item = ManualReviewItem.objects.select_for_update().get(pk=item_id)
    if item.state != ReviewState.OPEN:
        raise LabBankAPIException(
            code="CONFLICT",
            title="Resource conflict",
            detail=f"Review item cannot be claimed from state '{item.state}'.",
            status_code=status.HTTP_409_CONFLICT,
            type_slug="conflict",
        )

    item.state = ReviewState.CLAIMED
    item.claimed_by = actor
    item.claimed_at = timezone.now()
    item.save(update_fields=["state", "claimed_by", "claimed_at"])
    return item


@transaction.atomic
def decide_review_item(*, actor, item_id: UUID, decision: str, reason: str) -> ManualReviewItem:
    """Record a final APPROVE/REJECT decision on a claimed item and append a MANUAL_DECISION event."""
    _check_operator(actor)

    if decision not in (DecisionType.APPROVE, DecisionType.REJECT):
        raise LabBankAPIException(
            code="VALIDATION_ERROR",
            title="Invalid or incomplete input",
            detail="Manual decision must be APPROVE or REJECT.",
            status_code=status.HTTP_400_BAD_REQUEST,
            type_slug="validation-error",
        )

    item = (
        ManualReviewItem.objects.select_for_update(of=("self",))
        .select_related("assessment", "claimed_by")
        .get(pk=item_id)
    )
    if item.state == ReviewState.OPEN:
        raise LabBankAPIException(
            code="CONFLICT",
            title="Resource conflict",
            detail="Review item must be claimed before a decision can be recorded.",
            status_code=status.HTTP_409_CONFLICT,
            type_slug="conflict",
        )
    if item.state == ReviewState.DECIDED:
        raise LabBankAPIException(
            code="CONFLICT",
            title="Resource conflict",
            detail="Review item has already been decided.",
            status_code=status.HTTP_409_CONFLICT,
            type_slug="conflict",
        )
    if item.claimed_by_id != actor.pk:
        raise LabBankAPIException(
            code="FORBIDDEN",
            title="Access to resource is forbidden",
            detail="Only the operator who claimed this item may record a decision.",
            status_code=status.HTTP_403_FORBIDDEN,
            type_slug="forbidden",
        )

    item.state = ReviewState.DECIDED
    item.decided_at = timezone.now()
    item.save(update_fields=["state", "decided_at"])

    DecisionEvent.objects.create(
        assessment=item.assessment,
        transaction_id=item.transaction_id,
        event_type=EventType.MANUAL_DECISION,
        decision=decision,
        actor=actor.username,
        reason_code=f"MANUAL_{decision}",
        reason_message=reason,
        rule_snapshot=None,
        correlation_id=get_correlation_id() or "",
    )
    return item
