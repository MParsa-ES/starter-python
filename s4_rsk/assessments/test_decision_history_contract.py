import uuid
from datetime import UTC, datetime

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from assessments.models import DecisionEvent, DecisionType, EventType, RiskAssessment, TransferType
from common.openapi_contract import assert_response_matches

EVENTS_URL = "/api/v1/decision-events"
pytestmark = [pytest.mark.django_db, pytest.mark.openapi]


def _client_for(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def analyst(django_user_model):
    user = django_user_model.objects.create_user("history-contract-analyst")
    user.groups.add(Group.objects.get_or_create(name="analyst")[0])
    return user


@pytest.fixture
def client(analyst):
    return _client_for(analyst)


def _seed_event() -> DecisionEvent:
    assessment = RiskAssessment.objects.create(
        transaction_id=uuid.uuid4(),
        transfer_type=TransferType.INTERNAL,
        source_account_id=uuid.UUID("0192a7d1-0001-7000-8000-00000000a001"),
        destination_account_id=uuid.UUID("0192a7d1-0002-7000-8000-00000000a002"),
        destination_iban=None,
        amount=2_000_000,
        currency="IRR",
        occurred_at=datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC),
        input_fingerprint="1" * 64,
        decision=DecisionType.APPROVE,
    )
    return DecisionEvent.objects.create(
        assessment=assessment,
        transaction_id=assessment.transaction_id,
        event_type=EventType.INITIAL_EVALUATION,
        decision=DecisionType.APPROVE,
        actor="SYSTEM",
        reason_code="NO_RULE_MATCHED",
        reason_message="No blocking rule matched",
    )


def test_transaction_decisions_200_matches_contract(client):
    event = _seed_event()
    response = client.get(f"/api/v1/transactions/{event.transaction_id}/decisions")
    assert response.status_code == 200
    assert_response_matches(response, path_template="/transactions/{transaction_id}/decisions", method="get")


def test_transaction_decisions_404_matches_contract(client):
    response = client.get(f"/api/v1/transactions/{uuid.uuid4()}/decisions")
    assert response.status_code == 404
    assert_response_matches(response, path_template="/transactions/{transaction_id}/decisions", method="get")


def test_transaction_decisions_403_matches_contract(django_user_model):
    event = _seed_event()
    user = django_user_model.objects.create_user("history-contract-no-role")
    response = _client_for(user).get(f"/api/v1/transactions/{event.transaction_id}/decisions")
    assert response.status_code == 403
    assert_response_matches(response, path_template="/transactions/{transaction_id}/decisions", method="get")


def test_decision_events_search_200_matches_contract(client):
    _seed_event()
    response = client.get(EVENTS_URL, {"decision": "APPROVE"})
    assert response.status_code == 200
    assert_response_matches(response, path_template="/decision-events", method="get")


def test_decision_events_search_400_matches_contract(client):
    response = client.get(EVENTS_URL, {"from": "2026-10-25T00:00:00Z", "to": "2026-10-24T00:00:00Z"})
    assert response.status_code == 400
    assert_response_matches(response, path_template="/decision-events", method="get")


def test_decision_events_search_403_matches_contract(django_user_model):
    user = django_user_model.objects.create_user("events-contract-no-role")
    response = _client_for(user).get(EVENTS_URL)
    assert response.status_code == 403
    assert_response_matches(response, path_template="/decision-events", method="get")
