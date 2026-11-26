from uuid import uuid4

from assessments.models import DecisionReason
from assessments.serializers import DecisionReasonResponseSerializer


def test_rule_reason_exposes_captured_revision_and_snapshot():
    rule_id = uuid4()
    snapshot = {"name": "Limit", "parameters": {"max_amount": 100}, "revision": 3}
    reason = DecisionReason(
        code="AMOUNT_LIMIT_EXCEEDED",
        message="Amount exceeds limit",
        rule_id=rule_id,
        rule_revision=3,
        rule_snapshot=snapshot,
    )

    assert DecisionReasonResponseSerializer(reason).data == {
        "code": "AMOUNT_LIMIT_EXCEEDED",
        "message": "Amount exceeds limit",
        "rule_id": str(rule_id),
        "rule_revision": 3,
        "rule_snapshot": snapshot,
    }


def test_default_reason_does_not_invent_rule_details():
    reason = DecisionReason(code="NO_RULE_MATCHED", message="No blocking rule matched")

    assert DecisionReasonResponseSerializer(reason).data == {
        "code": "NO_RULE_MATCHED",
        "message": "No blocking rule matched",
    }
