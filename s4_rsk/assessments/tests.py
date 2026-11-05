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
    TransferType,
)

VALID_SOURCE_ACCOUNT_ID = "0192a7d1-0001-7000-8000-00000000a001"
VALID_DEST_ACCOUNT_ID = "0192a7d1-0002-7000-8000-00000000a002"
VALID_DEST_IBAN = "IR760990000000100324200002"


@pytest.fixture
def api_client(db) -> APIClient:
    client = APIClient()
    user = User.objects.create_user(
        username="s3-pay-service",
        password="test-password",
        is_staff=True,
    )
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def valid_internal_payload() -> dict:
    return {
        "transaction_id": str(uuid.uuid4()),
        "transfer_type": TransferType.INTERNAL,
        "source_account_id": VALID_SOURCE_ACCOUNT_ID,
        "destination_account_id": VALID_DEST_ACCOUNT_ID,
        "amount": 2_500_000,
        "currency": "IRR",
        "occurred_at": "2026-10-24T08:00:00Z",
    }


@pytest.fixture
def valid_external_payload() -> dict:
    return {
        "transaction_id": str(uuid.uuid4()),
        "transfer_type": TransferType.EXTERNAL,
        "source_account_id": VALID_SOURCE_ACCOUNT_ID,
        "destination_iban": VALID_DEST_IBAN,
        "amount": 5_000_000,
        "currency": "IRR",
        "occurred_at": "2026-10-24T08:05:00Z",
    }


@pytest.mark.django_db
class TestRiskAssessmentCreateAPI:
    """
    Tests for POST /api/v1/risk-assessments (US-01A).
    """

    def test_create_internal_assessment_success_persists_records(
        self, api_client: APIClient, valid_internal_payload: dict
    ):
        url = reverse("risk-assessment-create")
        correlation_id = "test-corr-id-001"

        response = api_client.post(
            url,
            data=valid_internal_payload,
            format="json",
            HTTP_X_CORRELATION_ID=correlation_id,
        )

        assert response.status_code == 201
        data = response.json()

        assert "decision_id" in data
        assert data["transaction_id"] == valid_internal_payload["transaction_id"]
        assert data["decision"] == DecisionType.APPROVE
        assert data["evaluated_at"].endswith("Z")
        assert data["reasons"] == [
            {
                "code": "NO_RULE_MATCHED",
                "message": "No blocking rule matched",
            }
        ]

        assessment = RiskAssessment.objects.get(decision_id=data["decision_id"])
        assert assessment.transfer_type == TransferType.INTERNAL
        assert str(assessment.source_account_id) == VALID_SOURCE_ACCOUNT_ID
        assert str(assessment.destination_account_id) == VALID_DEST_ACCOUNT_ID
        assert assessment.destination_iban is None
        assert assessment.destination_target == VALID_DEST_ACCOUNT_ID
        assert assessment.amount == 2_500_000
        assert assessment.currency == "IRR"
        assert len(assessment.input_fingerprint) == 64
        assert assessment.correlation_id == correlation_id

        assert DecisionReason.objects.filter(assessment=assessment).count() == 1
        event = DecisionEvent.objects.get(assessment=assessment)
        assert event.event_type == EventType.INITIAL_EVALUATION
        assert event.decision == DecisionType.APPROVE
        assert event.actor == "SYSTEM"

    def test_create_external_assessment_success_persists_records(
        self, api_client: APIClient, valid_external_payload: dict
    ):
        url = reverse("risk-assessment-create")

        response = api_client.post(url, data=valid_external_payload, format="json")

        assert response.status_code == 201
        data = response.json()

        assessment = RiskAssessment.objects.get(decision_id=data["decision_id"])
        assert assessment.transfer_type == TransferType.EXTERNAL
        assert str(assessment.source_account_id) == VALID_SOURCE_ACCOUNT_ID
        assert assessment.destination_account_id is None
        assert assessment.destination_iban == VALID_DEST_IBAN
        assert assessment.destination_target == VALID_DEST_IBAN

    def test_unauthenticated_request_returns_403(self, valid_internal_payload: dict):
        unauthenticated_client = APIClient()
        url = reverse("risk-assessment-create")

        response = unauthenticated_client.post(
            url, data=valid_internal_payload, format="json"
        )

        assert response.status_code == 403
        assert RiskAssessment.objects.count() == 0

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
            9_223_372_036_854_775_808,
        ],
    )
    def test_rejects_invalid_amount_types_and_boundaries(
        self, api_client: APIClient, valid_internal_payload: dict, invalid_amount
    ):
        url = reverse("risk-assessment-create")
        valid_internal_payload["amount"] = invalid_amount

        response = api_client.post(url, data=valid_internal_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_rejects_non_irr_currency(
        self, api_client: APIClient, valid_internal_payload: dict
    ):
        url = reverse("risk-assessment-create")
        valid_internal_payload["currency"] = "USD"

        response = api_client.post(url, data=valid_internal_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_rejects_internal_transfer_missing_destination_account_id(
        self, api_client: APIClient, valid_internal_payload: dict
    ):
        url = reverse("risk-assessment-create")
        valid_internal_payload.pop("destination_account_id")

        response = api_client.post(url, data=valid_internal_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_rejects_internal_transfer_with_destination_iban(
        self, api_client: APIClient, valid_internal_payload: dict
    ):
        url = reverse("risk-assessment-create")
        valid_internal_payload["destination_iban"] = VALID_DEST_IBAN

        response = api_client.post(url, data=valid_internal_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_rejects_identical_source_and_destination_account_id(
        self, api_client: APIClient, valid_internal_payload: dict
    ):
        url = reverse("risk-assessment-create")
        valid_internal_payload["destination_account_id"] = valid_internal_payload[
            "source_account_id"
        ]

        response = api_client.post(url, data=valid_internal_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_rejects_external_transfer_missing_destination_iban(
        self, api_client: APIClient, valid_external_payload: dict
    ):
        url = reverse("risk-assessment-create")
        valid_external_payload.pop("destination_iban")

        response = api_client.post(url, data=valid_external_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_rejects_external_transfer_with_destination_account_id(
        self, api_client: APIClient, valid_external_payload: dict
    ):
        url = reverse("risk-assessment-create")
        valid_external_payload["destination_account_id"] = VALID_DEST_ACCOUNT_ID

        response = api_client.post(url, data=valid_external_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    @pytest.mark.parametrize(
        "bad_iban",
        [
            # "IR000990000000100324200001",  # Invalid Mod-97 checksum
            "US060990000000100324200001",  # Wrong country code
            "IR0609900000001003242000",    # Too short
            "IR۰۶۰۹۹۰۰۰۰۰۰۰۱۰۰۳۲۴۲۰۰۰۰۱",  # Persian Unicode digits  # noqa: RUF001
        ],
    )
    def test_rejects_invalid_external_iban(
        self, api_client: APIClient, valid_external_payload: dict, bad_iban: str
    ):
        url = reverse("risk-assessment-create")
        valid_external_payload["destination_iban"] = bad_iban

        response = api_client.post(url, data=valid_external_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_rejects_naive_timestamp_without_timezone(
        self, api_client: APIClient, valid_internal_payload: dict
    ):
        url = reverse("risk-assessment-create")
        valid_internal_payload["occurred_at"] = "2026-10-24T08:00:00"

        response = api_client.post(url, data=valid_internal_payload, format="json")

        assert response.status_code == 400
        assert RiskAssessment.objects.count() == 0

    def test_atomic_rollback_on_internal_persistence_failure(
        self, api_client: APIClient, valid_internal_payload: dict
    ):
        url = reverse("risk-assessment-create")

        with (
            patch(
                "assessments.services.DecisionEvent.objects.create",
                side_effect=RuntimeError("Simulated DB failure"),
            ),
            pytest.raises(RuntimeError),
        ):
            api_client.post(url, data=valid_internal_payload, format="json")

        assert RiskAssessment.objects.count() == 0
        assert DecisionReason.objects.count() == 0
        assert DecisionEvent.objects.count() == 0


@pytest.mark.django_db
class TestRiskAssessmentDetailAPI:
    """
    Tests for GET /api/v1/risk-assessments/{decision_id} (US-01A).
    """

    def test_retrieve_existing_internal_assessment_returns_200(
        self, api_client: APIClient, valid_internal_payload: dict
    ):
        create_url = reverse("risk-assessment-create")
        create_resp = api_client.post(
            create_url, data=valid_internal_payload, format="json"
        )
        decision_id = create_resp.json()["decision_id"]

        detail_url = reverse(
            "risk-assessment-detail", kwargs={"decision_id": decision_id}
        )
        response = api_client.get(detail_url)

        assert response.status_code == 200
        data = response.json()
        assert data["decision_id"] == decision_id
        assert data["transaction_id"] == valid_internal_payload["transaction_id"]
        assert data["transfer_type"] == TransferType.INTERNAL
        assert data["source_account_id"] == VALID_SOURCE_ACCOUNT_ID
        assert data["destination_account_id"] == VALID_DEST_ACCOUNT_ID
        assert data["destination_iban"] is None
        assert data["amount"] == valid_internal_payload["amount"]
        assert data["currency"] == "IRR"
        assert data["decision"] == DecisionType.APPROVE

    def test_retrieve_unknown_decision_id_returns_404_rfc9457(
        self, api_client: APIClient
    ):
        unknown_id = uuid.uuid4()
        detail_url = reverse(
            "risk-assessment-detail", kwargs={"decision_id": unknown_id}
        )

        response = api_client.get(detail_url)

        assert response.status_code == 404
        assert response["Content-Type"].startswith("application/problem+json")
        problem = response.json()
        assert problem["status"] == 404
        assert problem["code"] == "NOT_FOUND"
