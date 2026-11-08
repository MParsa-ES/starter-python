from datetime import datetime, timedelta, timezone

import pytest

from assessments.models import DecisionType, RiskAssessment, TransferType
from dashboard.selectors import count_decisions_by_type

SOURCE_ACCOUNT_ID = "0192a7d1-0001-7000-8000-00000000a001"
DEST_ACCOUNT_ID = "0192a7d1-0002-7000-8000-00000000a002"


def create_assessment(tx_id: str, decision: str) -> RiskAssessment:
    now = datetime.now(timezone.utc)
    return RiskAssessment.objects.create(
        transaction_id=tx_id,
        transfer_type=TransferType.INTERNAL,
        source_account_id=SOURCE_ACCOUNT_ID,
        destination_account_id=DEST_ACCOUNT_ID,
        destination_iban=None,
        amount=2_500_000,
        currency="IRR",
        occurred_at=now,
        input_fingerprint=f"dummy_hash_{tx_id}",
        decision=decision,
    )


@pytest.mark.django_db
def test_count_decisions_by_type_groups_correctly():
    # Insert real records into PostgreSQL
    create_assessment("0192a7e4-6b1d-7c3e-9a41-2f5d8e0b7c11", DecisionType.APPROVE)
    create_assessment("0192a7e4-6b1d-7c3e-9a41-2f5d8e0b7c12", DecisionType.APPROVE)
    create_assessment("0192a7e4-6b1d-7c3e-9a41-2f5d8e0b7c13", DecisionType.REJECT)

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=1)
    end = now + timedelta(days=1)

    counts = count_decisions_by_type(start, end)

    assert counts.get("APPROVE") == 2
    assert counts.get("REJECT") == 1
    assert counts.get("REVIEW", 0) == 0


@pytest.mark.django_db
def test_count_decisions_by_type_respects_time_range():
    ra = create_assessment("0192a7e4-6b1d-7c3e-9a41-2f5d8e0b7c14", DecisionType.REVIEW)
    now = datetime.now(timezone.utc)

    ra.evaluated_at = now - timedelta(days=5)
    ra.save(update_fields=["evaluated_at"])

    counts_out = count_decisions_by_type(now - timedelta(days=2), now)
    assert counts_out.get("REVIEW", 0) == 0

    counts_in = count_decisions_by_type(now - timedelta(days=6), now)
    assert counts_in.get("REVIEW") == 1
