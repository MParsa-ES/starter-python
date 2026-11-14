"""Provider API tests: every response of the rule endpoints must match openapi/s4_rsk.yaml.

Run only these tests with:  pytest -m openapi -v
"""

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from common.openapi_contract import assert_payload_matches, assert_response_matches

from .models import RiskRule

URL = "/api/v1/risk-rules"
pytestmark = [pytest.mark.django_db, pytest.mark.openapi]


def _client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def manager(django_user_model):
    user = django_user_model.objects.create_user("contract-manager")
    user.groups.add(Group.objects.get_or_create(name="manager")[0])
    return user


@pytest.fixture
def client(manager):
    return _client_for(manager)


@pytest.fixture
def payload():
    return {"name": "contract limit", "type": "AMOUNT_LIMIT", "parameters": {"max_amount": 5_000_000}}


def _create(client, payload):
    response = client.post(URL, payload, format="json")
    assert response.status_code == 201
    return response.json()


def test_list_matches_contract(client, payload):
    _create(client, payload)
    response = client.get(URL)
    assert_response_matches(response, path_template="/risk-rules", method="get")
    assert response.status_code == 200


def test_create_matches_contract(client, payload):
    assert_payload_matches("RiskRuleInput", payload)
    response = client.post(URL, payload, format="json")
    assert_response_matches(response, path_template="/risk-rules", method="post")
    assert response.status_code == 201
    assert response.json()["revision"] == 1


def test_invalid_amount_is_documented_problem_details(client, payload):
    payload["parameters"] = {"max_amount": 0}
    response = client.post(URL, payload, format="json")
    assert_response_matches(response, path_template="/risk-rules", method="post")
    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_stale_revision_is_documented_conflict(client, payload):
    rule = _create(client, payload)
    response = client.patch(f"{URL}/{rule['id']}", {"expected_revision": 99, "name": "x"}, format="json")
    assert_response_matches(response, path_template="/risk-rules/{rule_id}", method="patch")
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_patch_success_matches_contract(client, payload):
    rule = _create(client, payload)
    body = {"expected_revision": 1, "parameters": {"max_amount": 9_000_000}}
    assert_payload_matches("RiskRulePatch", body)
    response = client.patch(f"{URL}/{rule['id']}", body, format="json")
    assert_response_matches(response, path_template="/risk-rules/{rule_id}", method="patch")
    assert response.json()["revision"] == 2


def test_audit_matches_contract(client, payload):
    rule = _create(client, payload)
    response = client.get(f"{URL}/{rule['id']}/audit")
    assert_response_matches(response, path_template="/risk-rules/{rule_id}/audit", method="get")
    assert response.status_code == 200


def test_unknown_rule_is_documented_not_found(client):
    response = client.patch(
        f"{URL}/019a0100-0000-7000-8000-00000000ffff", {"expected_revision": 1, "name": "x"}, format="json"
    )
    assert_response_matches(response, path_template="/risk-rules/{rule_id}", method="patch")
    assert response.status_code == 404


def test_missing_token_is_a_documented_401():
    response = APIClient().get(URL)
    assert response.status_code == 401
    assert_response_matches(response, path_template="/risk-rules", method="get")


def test_non_manager_is_a_documented_403(django_user_model):
    user = django_user_model.objects.create_user("contract-no-role")
    response = _client_for(user).get(URL)
    assert response.status_code == 403
    assert_response_matches(response, path_template="/risk-rules", method="get")


def test_idempotency_key_reuse_uses_the_code_named_in_the_contract(client, payload):
    key = "019a0100-0000-7000-8000-0000000000aa"
    assert client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key).status_code == 201
    response = client.post(URL, {**payload, "name": "other"}, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert_response_matches(response, path_template="/risk-rules", method="post")
    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert RiskRule.objects.count() == 1


def test_invalid_idempotency_key_is_a_validation_problem(client, payload):
    response = client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY="not-a-uuid")
    assert_response_matches(response, path_template="/risk-rules", method="post")
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert RiskRule.objects.count() == 0
