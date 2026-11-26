import uuid
from datetime import UTC, datetime

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from assessments.models import DecisionReason, RiskAssessment
from common.openapi_contract import assert_response_matches

pytestmark = pytest.mark.django_db


@pytest.fixture
def assessment():
    return RiskAssessment.objects.create(
        transaction_id=uuid.uuid4(), transfer_type="INTERNAL", source_account_id=uuid.uuid4(),
        destination_account_id=uuid.uuid4(), amount=100, currency="IRR",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC), input_fingerprint="0" * 64, decision="REJECT",
    )


def make_client(django_user_model, group):
    user = django_user_model.objects.create_user(f"explanation-{group}")
    if group:
        user.groups.add(Group.objects.get_or_create(name=group)[0])
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.parametrize("group", ["manager", "operator", "analyst"])
def test_authorized_roles_can_page_reasons_without_rule_parameters(assessment, django_user_model, group):
    rule_id = uuid.uuid4()
    for index in range(2):
        DecisionReason.objects.create(
            assessment=assessment, code=f"MATCH_{index}", message="Rule matched", rule_id=rule_id,
            rule_revision=2, rule_snapshot={"parameters": {"secret": "must not be exposed"}},
        )
    client = make_client(django_user_model, group)
    url = f"/api/v1/risk-assessments/{assessment.pk}/reasons"
    first = client.get(url, {"limit": 1})
    assert first.status_code == 200
    assert_response_matches(first, path_template="/risk-assessments/{decision_id}/reasons", method="get")
    assert first.data["items"] == [
        {"code": "MATCH_0", "message": "Rule matched", "rule_id": str(rule_id), "rule_revision": 2}
    ]
    second = client.get(url, {"limit": 1, "cursor": first.data["next_cursor"]})
    assert second.data["items"][0]["code"] == "MATCH_1"
    assert second.data["next_cursor"] is None
    assert "secret" not in str(first.data)


def test_permissions_missing_and_empty_assessments(assessment, django_user_model):
    url = f"/api/v1/risk-assessments/{assessment.pk}/reasons"
    assert APIClient().get(url).status_code == 401
    assert make_client(django_user_model, "payment_service").get(url).status_code == 403
    client = make_client(django_user_model, "manager")
    assert client.get(url).data == {"items": [], "next_cursor": None}
    assert client.get(f"/api/v1/risk-assessments/{uuid.uuid4()}/reasons").status_code == 404
