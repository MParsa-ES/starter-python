import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from common.openapi_contract import assert_payload_matches, assert_response_matches

URL = "/api/v1/blocked-identifiers"
VALID_IBAN = "IR760990000000100324200009"
pytestmark = [pytest.mark.django_db, pytest.mark.openapi]


def _client_for(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def manager(django_user_model):
    user = django_user_model.objects.create_user("blocklist-contract-manager")
    user.groups.add(Group.objects.get_or_create(name="manager")[0])
    return user


@pytest.fixture
def client(manager):
    return _client_for(manager)


@pytest.fixture
def payload() -> dict:
    return {
        "kind": "IBAN",
        "value": VALID_IBAN,
        "reason": "Sanctioned destination IBAN",
    }


def _create(client: APIClient, payload: dict) -> dict:
    response = client.post(URL, payload, format="json")
    assert response.status_code == 201
    return response.json()


def test_list_matches_contract(client, payload):
    _create(client, payload)
    response = client.get(URL, {"active": "true"})
    assert_response_matches(response, path_template="/blocked-identifiers", method="get")
    assert response.status_code == 200


def test_list_invalid_active_filter_matches_contract(client):
    response = client.get(URL, {"active": "not-a-bool"})
    assert_response_matches(response, path_template="/blocked-identifiers", method="get")
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_create_matches_contract(client, payload):
    assert_payload_matches("BlockedIdentifierInput", payload)
    response = client.post(URL, payload, format="json")
    assert_response_matches(response, path_template="/blocked-identifiers", method="post")
    assert response.status_code == 201


def test_create_invalid_iban_matches_contract(client, payload):
    response = client.post(URL, {**payload, "value": "INVALID"}, format="json")
    assert_response_matches(response, path_template="/blocked-identifiers", method="post")
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_create_duplicate_active_matches_conflict_contract(client, payload):
    _create(client, payload)
    response = client.post(URL, payload, format="json")
    assert_response_matches(response, path_template="/blocked-identifiers", method="post")
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_create_idempotency_key_reuse_matches_conflict_contract(client, payload):
    key = "019a0100-0000-7000-8000-0000000000bb"
    assert client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key).status_code == 201
    response = client.post(URL, {**payload, "reason": "Different reason"}, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert_response_matches(response, path_template="/blocked-identifiers", method="post")
    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_delete_matches_contract(client, payload):
    entry = _create(client, payload)
    response = client.delete(f"{URL}/{entry['id']}")
    assert_response_matches(response, path_template="/blocked-identifiers/{id}", method="delete")
    assert response.status_code == 204


def test_delete_unknown_id_matches_not_found_contract(client):
    response = client.delete(f"{URL}/019a0100-0000-7000-8000-00000000ffff")
    assert_response_matches(response, path_template="/blocked-identifiers/{id}", method="delete")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_non_manager_is_documented_403(django_user_model, payload):
    user = django_user_model.objects.create_user("blocklist-contract-no-role")
    non_manager_client = _client_for(user)

    get_res = non_manager_client.get(URL)
    assert get_res.status_code == 403
    assert_response_matches(get_res, path_template="/blocked-identifiers", method="get")

    post_res = non_manager_client.post(URL, payload, format="json")
    assert post_res.status_code == 403
    assert_response_matches(post_res, path_template="/blocked-identifiers", method="post")

    del_res = non_manager_client.delete(f"{URL}/019a0100-0000-7000-8000-00000000ffff")
    assert del_res.status_code == 403
    assert_response_matches(del_res, path_template="/blocked-identifiers/{id}", method="delete")
