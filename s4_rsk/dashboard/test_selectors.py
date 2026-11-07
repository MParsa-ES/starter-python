import pytest
from datetime import datetime, timezone, timedelta

from assessments.models import RiskAssessment, DecisionType
from dashboard.selectors import count_decisions_by_type


def create_assessment(tx_id, decision):
    """Helper to create a valid RiskAssessment hitting the actual DB."""
    now = datetime.now(timezone.utc)
    return RiskAssessment.objects.create(
        transaction_id=tx_id,
        amount=2500000,
        currency="IRR",
        source_iban="IR062960000000100324200001",
        destination_iban="IR062960000000100324200002",
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

    # Query the DB using our selector
    counts = count_decisions_by_type(start, end)

    assert counts.get("APPROVE") == 2
    assert counts.get("REJECT") == 1
    assert counts.get("REVIEW", 0) == 0


@pytest.mark.django_db
def test_count_decisions_by_type_respects_time_range():
    ra = create_assessment("0192a7e4-6b1d-7c3e-9a41-2f5d8e0b7c14", DecisionType.REVIEW)
    now = datetime.now(timezone.utc)

    # Manually shift the evaluated_at to 5 days ago to test range filtering
    ra.evaluated_at = now - timedelta(days=5)
    ra.save()

    # Query a range that does NOT include the item (e.g., last 2 days)
    counts_out = count_decisions_by_type(now - timedelta(days=2), now)
    assert counts_out.get("REVIEW", 0) == 0

    # Query a range that INCLUDES the item (e.g., last 6 days)
    counts_in = count_decisions_by_type(now - timedelta(days=6), now)
    assert counts_in.get("REVIEW") == 1