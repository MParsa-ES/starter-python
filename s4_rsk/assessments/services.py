import hashlib
import json
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from assessments.engine import (
    DEFAULT_APPROVE_CODE,
    DEFAULT_APPROVE_MESSAGE,
    EvaluationContext,
    evaluate_rules,
)
from assessments.models import (
    DecisionEvent,
    DecisionReason,
    EventType,
    RiskAssessment,
)
from common.middleware import get_correlation_id
from rules.selectors import list_active_rules

__all__ = [
    "DEFAULT_APPROVE_CODE",
    "DEFAULT_APPROVE_MESSAGE",
    "compute_input_fingerprint",
    "evaluate_and_persist_assessment",
]


def compute_input_fingerprint(payload: dict) -> str:
    """
    Computes a deterministic SHA-256 hash of the canonical request payload (Section 5).
    """
    canonical_dict = {
        "transaction_id": str(payload["transaction_id"]),
        "transfer_type": str(payload["transfer_type"]),
        "source_account_id": str(payload["source_account_id"]),
        "destination_account_id": (
            str(payload["destination_account_id"])
            if payload.get("destination_account_id") is not None
            else None
        ),
        "destination_iban": payload.get("destination_iban"),
        "amount": int(payload["amount"]),
        "currency": str(payload["currency"]),
        "occurred_at": payload["occurred_at"].isoformat(),
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


@transaction.atomic
def evaluate_and_persist_assessment(
    *,
    transaction_id: UUID,
    transfer_type: str,
    source_account_id: UUID,
    destination_account_id: UUID | None = None,
    destination_iban: str | None = None,
    amount: int,
    currency: str,
    occurred_at,
) -> RiskAssessment:
    """
    US-01B Core Rule Engine Evaluation:
    Evaluates the transfer against active RiskRules and atomically persists
    RiskAssessment, all DecisionReasons, and the initial DecisionEvent.
    """
    payload = {
        "transaction_id": transaction_id,
        "transfer_type": transfer_type,
        "source_account_id": source_account_id,
        "destination_account_id": destination_account_id,
        "destination_iban": destination_iban,
        "amount": amount,
        "currency": currency,
        "occurred_at": occurred_at,
    }
    fingerprint = compute_input_fingerprint(payload)
    correlation_id = get_correlation_id() or ""
    evaluated_at = timezone.now()

    ctx = EvaluationContext(
        transaction_id=transaction_id,
        transfer_type=transfer_type,
        source_account_id=source_account_id,
        destination_account_id=destination_account_id,
        destination_iban=destination_iban,
        amount=amount,
        currency=currency,
    )
    active_rules = list_active_rules(as_of=evaluated_at)
    result = evaluate_rules(ctx, active_rules)
    primary = result.primary_reason

    assessment = RiskAssessment.objects.create(
        transaction_id=transaction_id,
        transfer_type=transfer_type,
        source_account_id=source_account_id,
        destination_account_id=destination_account_id,
        destination_iban=destination_iban,
        amount=amount,
        currency=currency,
        occurred_at=occurred_at,
        input_fingerprint=fingerprint,
        decision=result.decision,
        correlation_id=correlation_id,
    )

    DecisionReason.objects.bulk_create(
        [
            DecisionReason(
                assessment=assessment,
                code=reason.code,
                message=reason.message,
                rule_id=reason.rule_id,
                rule_revision=reason.rule_revision,
                rule_snapshot=reason.rule_snapshot,
            )
            for reason in result.reasons
        ]
    )

    DecisionEvent.objects.create(
        assessment=assessment,
        transaction_id=transaction_id,
        event_type=EventType.INITIAL_EVALUATION,
        decision=result.decision,
        actor="SYSTEM",
        reason_code=primary.code,
        reason_message=primary.message,
        rule_snapshot=primary.rule_snapshot,
        correlation_id=correlation_id,
    )

    return RiskAssessment.objects.prefetch_related("reasons").get(
        decision_id=assessment.decision_id
    )
