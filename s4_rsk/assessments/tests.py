import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from assessments.models import (
    DecisionEvent,
    DecisionReason,
    DecisionType,
    EventType,
    RiskAssessment,
)

# Valid Iranian IBANs (Bank code 099)
VALID_SOURCE_IBAN = "IR060990000000100324200001"
VALID_DEST_IBAN = "IR760990000000100324200002"


@pytest.fixture
def api_client(db) -> APIClient:
    """
    Returns an authenticated DRF APIClient so requests pass the global
    IsAuthenticated permission gate (FIX-10).
    """
    client = APIClient()
    user = User.objects.create_user(
        username="s3-pay-service",
        password="test-password",
        is_staff=True,
    )
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def valid_payload() -> dict:
    return {
        "transaction_id": str(uuid.uuid4()),
        "amount": 2_500_000,
        "currency": "IRR",
        "source_iban": VALID_SOURCE_IBAN,
        "destination_iban": VALID_DEST_IBAN,
        "occurred_at": "2026-10-24T08:00:00Z",
    }


@pytest.mark.django_db
class TestRiskAssessmentCreateAPI:
    """
    Tests for POST /api/v1/risk-assessments (US-01A).
    """

    def test_unauthenticated_request_returns_403(self, valid_payload: dict):
        """
        Verifies that unauthenticated callers are rejected with 403 Forbidden (FIX-07 / FIX-10).
        """
        unauthenticated_client = APIClient()
        url = reverse("risk-assessment-create")

        response = unauthenticated_client.post(url, data=valid_payload, format="json")

        assert response.status_code == 403
        assert RiskAssessment.objects.count() == 0

    def test_create_assessment_success_persists_records(self, api_client: APIClient, valid_payload: dict):
        url = reverse("risk-assessment-create")
        correlation_id = "test-corr-id-001"

        response = api_client.post(
            url,
            data=valid_payload,
            format="json",
            HTTP_X_CORRELATION_ID=correlation_id,
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response contract (Section 6)
        assert "decision_id" in data
        assert data["transaction_id"] == valid_payload["transaction_id"]
        assert data["decision"] == DecisionType.APPROVE
        assert data["evaluated_at"].endswith("Z")
        assert data["reasons"] == [
            {
                "code": "NO_RULE_MATCHED",
                "message": "No blocking rule matched",
            }
        ]

        # Verify database persistence across all 3 tables
        assessment = RiskAssessment.objects.get(decision_id=data["decision_id"])
        assert str(assessment.transaction_id) == valid_payload["transaction_id"]
        assert assessment.amount == 2_500_000
        assert assessment.currency == "IRR"
        assert assessment.source_iban == VALID_SOURCE_IBAN
        assert assessment.destination_iban == VALID_DEST_IBAN
        assert len(assessment.input_fingerprint) == 64
        assert assessment.correlation_id == correlation_id

        reasons = DecisionReason.objects.filter(assessment=assessment)
        assert reasons.count() == 1
        assert reasons.first().code == "NO_RULE_MATCHED"

        events = DecisionEvent.objects.filter(assessment=assessment)
        assert events.count() == 1
        event = events.first()
        assert event.event_type == EventType.INITIAL_EVALUATION
        assert event.decision == DecisionType.APPROVE
        assert event.actor == "SYSTEM"
        assert event.reason_code == "NO_RULE_MATCHED"

    @pytest.mark.parametrize(
        "invalid_amount",
        [
            0,
            -1,
            -500_000,
            True,
            False,
            2500.50,
            "2500000",
            9_223_372_036_854_775_808,  # int64 overflow (MAX_INT64 + 1)
        ],
    )
    def test_rejects_invalid_amount_types_and_boundaries(
        self, api_client: APIClient, valid_payload: dict, invalid_amount
    ):
        url = reverse("risk-assessment-create")
        valid_payload["amount"] = invalid_amount

        response = api_client.post(url, data=valid_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0
        assert DecisionReason.objects.count() == 0
        assert DecisionEvent.objects.count() == 0

    def test_rejects_non_irr_currency(self, api_client: APIClient, valid_payload: dict):
        url = reverse("risk-assessment-create")
        valid_payload["currency"] = "USD"

        response = api_client.post(url, data=valid_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    @pytest.mark.parametrize(
        "bad_iban",
        [
            "US060990000000100324200001",  # Wrong country code
            "IR0609900000001003242000",  # Too short (24 chars instead of 26)
            "IR۰۶۰۹۹۰۰۰۰۰۰۰۱۰۰۳۲۴۲۰۰۰۰۱",  # Persian Unicode digits  # noqa: RUF001
        ],
    )
    def test_rejects_invalid_iban(self, api_client: APIClient, valid_payload: dict, bad_iban: str):
        url = reverse("risk-assessment-create")
        valid_payload["source_iban"] = bad_iban

        response = api_client.post(url, data=valid_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_rejects_identical_source_and_destination_iban(self, api_client: APIClient, valid_payload: dict):
        url = reverse("risk-assessment-create")
        valid_payload["destination_iban"] = valid_payload["source_iban"]

        response = api_client.post(url, data=valid_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_rejects_naive_timestamp_without_timezone(self, api_client: APIClient, valid_payload: dict):
        url = reverse("risk-assessment-create")
        valid_payload["occurred_at"] = "2026-10-24T08:00:00"  # Missing 'Z' or offset

        response = api_client.post(url, data=valid_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_atomic_rollback_on_internal_persistence_failure(self, api_client: APIClient, valid_payload: dict):
        """
        Ensures that if DecisionEvent creation fails, the entire transaction rolls back
        and no orphan RiskAssessment or DecisionReason remains in PostgreSQL.
        """
        url = reverse("risk-assessment-create")

        with (
            patch(
                "assessments.services.DecisionEvent.objects.create",
                side_effect=RuntimeError("Simulated DB failure"),
            ),
            pytest.raises(RuntimeError),
        ):
            api_client.post(url, data=valid_payload, format="json")

        assert RiskAssessment.objects.count() == 0
        assert DecisionReason.objects.count() == 0
        assert DecisionEvent.objects.count() == 0


@pytest.mark.django_db
class TestRiskAssessmentDetailAPI:
    """
    Tests for GET /api/v1/risk-assessments/{decision_id} (US-01A).
    """

    def test_retrieve_existing_assessment_returns_200(self, api_client: APIClient, valid_payload: dict):
        create_url = reverse("risk-assessment-create")
        create_resp = api_client.post(create_url, data=valid_payload, format="json")
        decision_id = create_resp.json()["decision_id"]

        detail_url = reverse("risk-assessment-detail", kwargs={"decision_id": decision_id})
        response = api_client.get(detail_url)

        assert response.status_code == 200
        data = response.json()
        assert data["decision_id"] == decision_id
        assert data["transaction_id"] == valid_payload["transaction_id"]
        assert data["amount"] == valid_payload["amount"]
        assert data["currency"] == "IRR"
        assert data["source_iban"] == VALID_SOURCE_IBAN
        assert data["destination_iban"] == VALID_DEST_IBAN
        assert data["decision"] == DecisionType.APPROVE
        assert len(data["reasons"]) == 1
        assert data["reasons"][0]["code"] == "NO_RULE_MATCHED"

    def test_retrieve_unknown_decision_id_returns_404_rfc9457(self, api_client: APIClient):
        unknown_id = uuid.uuid4()
        detail_url = reverse("risk-assessment-detail", kwargs={"decision_id": unknown_id})

        response = api_client.get(detail_url)

        assert response.status_code == 404
        assert response["Content-Type"].startswith("application/problem+json")
        problem = response.json()
        assert problem["status"] == 404
        assert problem["code"] == "NOT_FOUND"
