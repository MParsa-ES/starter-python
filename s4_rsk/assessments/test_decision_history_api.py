import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.db import DatabaseError, connection, transaction
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from assessments.models import (
    DecisionEvent,
    DecisionType,
    EventType,
    RiskAssessment,
    TransferType,
)

EVENTS_URL = "/api/v1/decision-events"
SOURCE_ACCOUNT_ID = "0192a7d1-0001-7000-8000-00000000a001"
DEST_ACCOUNT_ID = "0192a7d1-0002-7000-8000-00000000a002"

pytestmark = pytest.mark.django_db


def _auth_client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def _user_with_group(django_user_model, username: str, group_name: str | None = None):
    user = django_user_model.objects.create_user(username)
    if group_name is not None:
        user.groups.add(Group.objects.get_or_create(name=group_name)[0])
    return user


def _create_assessment(
    *,
    transaction_id: uuid.UUID | None = None,
    decision: str = DecisionType.REVIEW,
) -> RiskAssessment:
    return RiskAssessment.objects.create(
        transaction_id=transaction_id or uuid.uuid4(),
        transfer_type=TransferType.INTERNAL,
        source_account_id=uuid.UUID(SOURCE_ACCOUNT_ID),
        destination_account_id=uuid.UUID(DEST_ACCOUNT_ID),
        destination_iban=None,
        amount=1_000_000,
        currency="IRR",
        occurred_at=datetime(2026, 10, 24, 8, 0, 0, tzinfo=UTC),
        input_fingerprint="0" * 64,
        decision=decision,
    )


def _create_event(
    *,
    assessment: RiskAssessment,
    created_at: datetime,
    event_type: str = EventType.INITIAL_EVALUATION,
    decision: str = DecisionType.REVIEW,
    actor: str = "SYSTEM",
    reason_code: str = "AMOUNT_LIMIT_EXCEEDED",
    reason_message: str = "Transaction flagged for review.",
) -> DecisionEvent:
    with patch("django.utils.timezone.now", return_value=created_at):
        return DecisionEvent.objects.create(
            assessment=assessment,
            transaction_id=assessment.transaction_id,
            event_type=event_type,
            decision=decision,
            actor=actor,
            reason_code=reason_code,
            reason_message=reason_message,
        )


@pytest.fixture
def manager_client(django_user_model) -> APIClient:
    return _auth_client(_user_with_group(django_user_model, "history-manager", "manager"))


def test_transaction_history_returns_append_only_events_oldest_first(manager_client):
    tx_id = uuid.uuid4()
    assessment = _create_assessment(transaction_id=tx_id, decision=DecisionType.REVIEW)
    other_assessment = _create_assessment(decision=DecisionType.APPROVE)

    t1 = datetime(2026, 10, 24, 9, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 10, 24, 9, 15, 0, tzinfo=UTC)

    ev1 = _create_event(
        assessment=assessment,
        created_at=t1,
        event_type=EventType.INITIAL_EVALUATION,
        decision=DecisionType.REVIEW,
        actor="SYSTEM",
        reason_code="DAILY_VELOCITY_LIMIT_EXCEEDED",
        reason_message="Needs manual check.",
    )
    ev2 = _create_event(
        assessment=assessment,
        created_at=t2,
        event_type=EventType.MANUAL_DECISION,
        decision=DecisionType.APPROVE,
        actor="operator-42",
        reason_code="OPERATOR_VERIFIED",
        reason_message="Verified with customer.",
    )
    _create_event(
        assessment=other_assessment,
        created_at=t1,
        decision=DecisionType.APPROVE,
        reason_code="NO_RULE_MATCHED",
    )

    response = manager_client.get(f"/api/v1/transactions/{tx_id}/decisions")
    assert response.status_code == 200
    assert response["X-Correlation-ID"]
    assert response.data["next_cursor"] is None

    items = response.data["items"]
    assert [item["event_id"] for item in items] == [str(ev1.event_id), str(ev2.event_id)]
    assert items[0]["decision_id"] == str(assessment.decision_id)
    assert items[0]["transaction_id"] == str(tx_id)
    assert items[0]["event_type"] == EventType.INITIAL_EVALUATION
    assert items[0]["decision"] == DecisionType.REVIEW
    assert items[0]["actor"] == "SYSTEM"
    assert items[1]["event_type"] == EventType.MANUAL_DECISION
    assert items[1]["decision"] == DecisionType.APPROVE
    assert items[1]["actor"] == "operator-42"


def test_transaction_history_cursor_pagination(manager_client):
    tx_id = uuid.uuid4()
    assessment = _create_assessment(transaction_id=tx_id)
    created_ids = []
    for minute in (1, 2, 3):
        ev = _create_event(
            assessment=assessment,
            created_at=datetime(2026, 10, 24, 10, minute, 0, tzinfo=UTC),
            event_type=EventType.INITIAL_EVALUATION if minute == 1 else EventType.MANUAL_DECISION,
        )
        created_ids.append(str(ev.event_id))

    page1 = manager_client.get(f"/api/v1/transactions/{tx_id}/decisions", {"limit": 2})
    assert page1.status_code == 200
    assert len(page1.data["items"]) == 2
    assert page1.data["next_cursor"] is not None

    page2 = manager_client.get(
        f"/api/v1/transactions/{tx_id}/decisions",
        {"limit": 2, "cursor": page1.data["next_cursor"]},
    )
    assert page2.status_code == 200
    assert len(page2.data["items"]) == 1
    assert page2.data["next_cursor"] is None

    seen = [item["event_id"] for item in page1.data["items"]] + [item["event_id"] for item in page2.data["items"]]
    assert seen == created_ids


def test_transaction_history_unknown_transaction_returns_404(manager_client):
    missing_tx = uuid.uuid4()
    response = manager_client.get(f"/api/v1/transactions/{missing_tx}/decisions")
    assert response.status_code == 404
    assert response["Content-Type"] == "application/problem+json"
    assert response.data["code"] == "NOT_FOUND"


def test_decision_events_search_filters_by_decision_and_half_open_range(manager_client):
    t0 = datetime(2026, 10, 24, 7, 59, 59, tzinfo=UTC)
    t1 = datetime(2026, 10, 24, 8, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)
    t3 = datetime(2026, 10, 25, 0, 0, 0, tzinfo=UTC)

    ev0 = _create_event(assessment=_create_assessment(), created_at=t0, decision=DecisionType.APPROVE)
    ev1 = _create_event(assessment=_create_assessment(), created_at=t1, decision=DecisionType.REJECT)
    ev2 = _create_event(assessment=_create_assessment(), created_at=t2, decision=DecisionType.REVIEW)
    ev3 = _create_event(assessment=_create_assessment(), created_at=t3, decision=DecisionType.REJECT)

    all_res = manager_client.get(EVENTS_URL)
    assert all_res.status_code == 200
    assert [i["event_id"] for i in all_res.data["items"]] == [
        str(ev3.event_id),
        str(ev2.event_id),
        str(ev1.event_id),
        str(ev0.event_id),
    ]

    range_res = manager_client.get(
        EVENTS_URL,
        {"from": "2026-10-24T08:00:00Z", "to": "2026-10-25T00:00:00Z"},
    )
    assert range_res.status_code == 200
    assert [i["event_id"] for i in range_res.data["items"]] == [str(ev2.event_id), str(ev1.event_id)]

    combined_res = manager_client.get(
        EVENTS_URL,
        {"decision": "REJECT", "from": "2026-10-24T08:00:00Z", "to": "2026-10-25T00:00:00Z"},
    )
    assert combined_res.status_code == 200
    assert [i["event_id"] for i in combined_res.data["items"]] == [str(ev1.event_id)]

    empty_res = manager_client.get(
        EVENTS_URL,
        {"from": "2026-10-24T08:00:00Z", "to": "2026-10-24T08:00:00Z"},
    )
    assert empty_res.status_code == 200
    assert empty_res.data["items"] == []

    tz_res = manager_client.get(
        EVENTS_URL,
        {"from": "2026-10-24T11:30:00+03:30", "to": "2026-10-24T15:30:00+03:30"},
    )
    assert tz_res.status_code == 200
    assert [i["event_id"] for i in tz_res.data["items"]] == [str(ev1.event_id)]


def test_decision_events_search_cursor_pagination(manager_client):
    created_ids = []
    for minute in (1, 2, 3):
        ev = _create_event(
            assessment=_create_assessment(),
            created_at=datetime(2026, 10, 24, 14, minute, 0, tzinfo=UTC),
            decision=DecisionType.APPROVE,
        )
        created_ids.append(str(ev.event_id))

    page1 = manager_client.get(EVENTS_URL, {"limit": 2})
    assert page1.status_code == 200
    assert len(page1.data["items"]) == 2
    assert page1.data["next_cursor"] is not None

    page2 = manager_client.get(EVENTS_URL, {"limit": 2, "cursor": page1.data["next_cursor"]})
    assert page2.status_code == 200
    assert len(page2.data["items"]) == 1
    assert page2.data["next_cursor"] is None

    seen = [i["event_id"] for i in page1.data["items"]] + [i["event_id"] for i in page2.data["items"]]
    assert seen == list(reversed(created_ids))


@pytest.mark.parametrize(
    "params",
    [
        {"decision": "UNKNOWN"},
        {"from": "2026-10-25T00:00:00Z", "to": "2026-10-24T00:00:00Z"},
        {"from": "2026-10-24T08:00:00"},
        {"to": "2026-10-24T08:00:00"},
        {"from": "not-a-timestamp"},
    ],
)
def test_decision_events_search_rejects_invalid_query_params(manager_client, params):
    response = manager_client.get(EVENTS_URL, params)
    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"
    assert response.data["code"] == "VALIDATION_ERROR"


def test_rbac_allows_manager_operator_analyst_and_denies_others(django_user_model):
    tx_id = uuid.uuid4()
    _create_event(
        assessment=_create_assessment(transaction_id=tx_id),
        created_at=datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC),
    )
    tx_url = f"/api/v1/transactions/{tx_id}/decisions"

    # Unauthenticated -> 401
    anon = APIClient()
    assert anon.get(tx_url).status_code == 401
    assert anon.get(EVENTS_URL).status_code == 401

    # Allowed roles -> 200
    for role in ("manager", "operator", "analyst"):
        client = _auth_client(_user_with_group(django_user_model, f"user-{role}", role))
        assert client.get(tx_url).status_code == 200
        assert client.get(EVENTS_URL).status_code == 200

    # Forbidden roles -> 403
    for username, role in (("no-role-user", None), ("s3-pay-no-history", "payment_service")):
        client = _auth_client(_user_with_group(django_user_model, username, role))
        assert client.get(tx_url).status_code == 403
        assert client.get(EVENTS_URL).status_code == 403


def test_database_rejects_decision_event_update_and_delete():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL append-only trigger")

    _create_event(
        assessment=_create_assessment(),
        created_at=datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC),
    )

    for mutation in (
        lambda: DecisionEvent.objects.update(reason_code="TAMPERED"),
        lambda: DecisionEvent.objects.all().delete(),
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            mutation()

    assert DecisionEvent.objects.count() == 1


def test_end_to_end_assessment_creation_appears_in_decision_history(django_user_model):
    pay_client = _auth_client(_user_with_group(django_user_model, "s3-pay-e2e", "payment_service"))
    analyst_client = _auth_client(_user_with_group(django_user_model, "risk-analyst-e2e", "analyst"))

    tx_id = str(uuid.uuid4())
    created = pay_client.post(
        reverse("risk-assessment-create"),
        {
            "transaction_id": tx_id,
            "transfer_type": TransferType.INTERNAL,
            "source_account_id": SOURCE_ACCOUNT_ID,
            "destination_account_id": DEST_ACCOUNT_ID,
            "amount": 500_000,
            "currency": "IRR",
            "occurred_at": "2026-10-24T11:00:00Z",
        },
        format="json",
    )
    assert created.status_code == 201
    decision_id = created.data["decision_id"]

    tx_history = analyst_client.get(f"/api/v1/transactions/{tx_id}/decisions")
    assert tx_history.status_code == 200
    assert len(tx_history.data["items"]) == 1
    assert tx_history.data["items"][0]["decision_id"] == decision_id
    assert tx_history.data["items"][0]["event_type"] == EventType.INITIAL_EVALUATION
    assert tx_history.data["items"][0]["actor"] == "SYSTEM"

    search = analyst_client.get(EVENTS_URL, {"decision": DecisionType.APPROVE})
    assert search.status_code == 200
    assert any(item["decision_id"] == decision_id for item in search.data["items"])
