import hashlib
import json
import os
from datetime import UTC
from uuid import UUID

from django.conf import settings
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
from integrations.ledger_client import LedgerClient, LedgerHistory, assess_ledger_history
from rules.selectors import list_active_rules

__all__ = [
    "DEFAULT_APPROVE_CODE",
    "DEFAULT_APPROVE_MESSAGE",
    "compute_input_fingerprint",
    "evaluate_and_persist_assessment",
]


def _build_ledger_client() -> LedgerClient | None:
    base_url = os.environ.get("NEIGHBOR_BASE_URL") or os.environ.get("S2_LDG_BASE_URL")
    if not base_url:
        return None
    token = os.environ.get("S2_LDG_TOKEN") or None
    return LedgerClient(base_url=base_url, token=token)


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
    ledger_client: LedgerClient | None = None,
) -> RiskAssessment:
    """
    US-01B Risk Assessment Service:
    Queries S2-LDG debit history (when configured), evaluates active RiskRules,
    and atomically persists RiskAssessment, DecisionReasons, and DecisionEvent.
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

    client = ledger_client if ledger_client is not None else _build_ledger_client()
    ledger_history: LedgerHistory | None = None
    if client is not None:
        tehran_now = evaluated_at.astimezone(settings.BUSINESS_TIMEZONE)
        tehran_day_start = tehran_now.replace(hour=0, minute=0, second=0, microsecond=0)
        since_utc = tehran_day_start.astimezone(UTC)
        ledger_history = assess_ledger_history(
            client,
            source_account_id,
            since_utc,
            correlation_id=correlation_id,
        )

    ctx = EvaluationContext(
        transaction_id=transaction_id,
        transfer_type=transfer_type,
        source_account_id=source_account_id,
        destination_account_id=destination_account_id,
        destination_iban=destination_iban,
        amount=amount,
        currency=currency,
        ledger_history=ledger_history,
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
