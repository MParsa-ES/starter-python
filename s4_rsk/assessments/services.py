import hashlib
import json
from uuid import UUID

from django.db import transaction

from assessments.models import (
    DecisionEvent,
    DecisionReason,
    DecisionType,
    EventType,
    RiskAssessment,
)
from common.middleware import get_correlation_id

DEFAULT_APPROVE_CODE = "NO_RULE_MATCHED"
DEFAULT_APPROVE_MESSAGE = "No blocking rule matched"

def compute_input_fingerprint(payload:dict) -> str :
    """
    Computes a deterministic SHA-256 hash of the canonical request payload
    :param payload:
    :return:
    """

    canonical_dict = {
        "transaction_id": str(payload["transaction_id"]),
        "amount": int(payload["amount"]),
        "currency": str(payload["currency"]),
        "source_iban":str(payload["source_iban"]),
        "destination_iban":str(payload["destination_iban"]),
        "occurred_at":payload["occurred_at"].isoformat(),
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

@transaction.atomic
def evaluate_and_persist_assessment(
        *,transaction_id:UUID,
        amount:int,
        currency:str,
        source_iban:str,
        destination_iban:str,
        occurred_at) -> RiskAssessment :
    """
    US-01A Base Risk Assessment Service:
    Atomically evaluates the request using the base policy (APPROVE / NO_RULE_MATCHED)
    and persists RiskAssessment, DecisionReason, and initial DecisionEvent in one transaction.
    :param transaction_id:
    :param amount:
    :param currency:
    :param source_iban:
    :param destination_iban:
    :param occurred_at:
    :return:
    """
    payload = {
        "transaction_id": transaction_id,
        "amount": amount,
        "currency": currency,
        "source_iban": source_iban,
        "destination_iban": destination_iban,
        "occurred_at": occurred_at,
    }

    fingerprint = compute_input_fingerprint(payload)
    correlation_id = get_correlation_id() or ""

    # TODO: Base policy for US-01A (Rule evaluators plug in here in US-01B)
    decision = DecisionType.APPROVE
    reason_code = DEFAULT_APPROVE_CODE
    reason_message = DEFAULT_APPROVE_MESSAGE

    assessment = RiskAssessment.objects.create(
        transaction_id=transaction_id,
        amount=amount,
        currency=currency,
        source_iban=source_iban,
        destination_iban=destination_iban,
        occurred_at=occurred_at,
        input_fingerprint=fingerprint,
        decision=decision,
        correlation_id=correlation_id,
    )

    DecisionReason.objects.create(
        assessment=assessment,
        code=reason_code,
        message=reason_message,
        rule_id=None,
        rule_revision=None,
        rule_snapshot=None,
    )

    DecisionEvent.objects.create(
        assessment=assessment,
        transaction_id=transaction_id,
        event_type=EventType.INITIAL_EVALUATION,
        decision=decision,
        actor="SYSTEM",
        reason_code=reason_code,
        reason_message=reason_message,
        rule_snapshot=None,
        correlation_id=correlation_id,
    )

    return RiskAssessment.objects.prefetch_related("reasons").get(
        decision_id=assessment.decision_id
    )
