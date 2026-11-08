import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth.models import Group
from django.db import DatabaseError, connection, transaction
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import RiskRule, RuleRevision

URL = "/api/v1/risk-rules"
pytestmark = pytest.mark.django_db


@pytest.fixture
def client_manager(django_user_model):
    user = django_user_model.objects.create_user("api-manager")
    user.groups.add(Group.objects.get_or_create(name="manager")[0])
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client, user


@pytest.fixture
def payload():
    return {"name": "limit", "type": "AMOUNT_LIMIT", "parameters": {"max_amount": 100}}


def test_create_update_and_read_audit(client_manager, payload):
    client, user = client_manager
    created = client.post(URL, payload, format="json")
    assert created.status_code == 201
    rule_id = created.data["id"]
    assert created.data["revision"] == 1
    changed = client.patch(
        f"{URL}/{rule_id}", {"expected_revision": 1, "parameters": {"max_amount": 200}}, format="json"
    )
    assert changed.status_code == 200
    assert changed.data["revision"] == 2
    history = client.get(f"{URL}/{rule_id}/audit").data["items"]
    assert [item["revision"] for item in history] == [2, 1]
    assert history[0]["actor"] == str(user.pk)
    assert history[0]["before"]["parameters"] == {"max_amount": 100}
    assert history[0]["after"]["parameters"] == {"max_amount": 200}
    assert history[1]["before"] is None


def test_post_replay_and_conflict(client_manager, payload):
    client, _ = client_manager
    key = str(uuid.uuid4())
    first = client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
    replay = client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert first.status_code == replay.status_code == 201
    assert first.data == replay.data
    conflict = client.post(URL, {**payload, "name": "different"}, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert conflict.status_code == 409
    assert conflict.data["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert conflict["Content-Type"] == "application/problem+json"
    invalid_body = client.post(URL, {}, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert invalid_body.status_code == 409
    assert invalid_body.data["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert RiskRule.objects.count() == RuleRevision.objects.count() == 1


def test_same_key_cannot_leak_response_to_another_manager(client_manager, payload, django_user_model):
    client, _ = client_manager
    key = str(uuid.uuid4())
    assert client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key).status_code == 201
    other = django_user_model.objects.create_user("other-manager")
    other.groups.add(Group.objects.get(name="manager"))
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(other)}")
    response = client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert response.status_code == 409
    assert response.data["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_invalid_first_request_does_not_consume_idempotency_key(client_manager, payload):
    client, _ = client_manager
    key = str(uuid.uuid4())
    assert client.post(URL, {}, format="json", HTTP_IDEMPOTENCY_KEY=key).status_code == 400
    assert client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key).status_code == 201


@pytest.mark.parametrize(
    "parameters",
    [{}, {"max_amount": 0}, {"max_amount": -1}, {"max_amount": True}, {"max_amount": 2**63}, []],
)
def test_invalid_parameters_rejected_without_side_effects(client_manager, payload, parameters):
    client, _ = client_manager
    response = client.post(URL, {**payload, "parameters": parameters}, format="json")
    assert response.status_code == 400
    assert not RiskRule.objects.exists()
    assert not RuleRevision.objects.exists()


def test_stale_and_invalid_patch_leave_original_unchanged(client_manager, payload):
    client, _ = client_manager
    rule_id = client.post(URL, payload, format="json").data["id"]
    stale = client.patch(f"{URL}/{rule_id}", {"expected_revision": 2, "name": "new"}, format="json")
    assert stale.status_code == 409
    assert stale.data["code"] == "CONFLICT"
    assert (
        client.patch(
            f"{URL}/{rule_id}", {"expected_revision": 1, "parameters": {"max_amount": 0}}, format="json"
        ).status_code
        == 400
    )
    assert client.patch(f"{URL}/{rule_id}", {"expected_revision": 1, "actor": 1}, format="json").status_code == 400
    assert (
        client.patch(f"{URL}/{rule_id}", {"expected_revision": True, "name": "bad"}, format="json").status_code == 400
    )
    rule = RiskRule.objects.get(pk=rule_id)
    assert (rule.revision, rule.name, rule.history.count()) == (1, "limit", 1)


def test_auth_and_missing_rule(client_manager, payload, django_user_model):
    client, _ = client_manager
    missing = uuid.uuid4()
    assert client.get(f"{URL}/{missing}/audit").status_code == 404
    assert client.patch(f"{URL}/{missing}", {"expected_revision": 1, "name": "x"}, format="json").status_code == 404
    assert APIClient().post(URL, payload, format="json").status_code == 401
    other = django_user_model.objects.create_user("ordinary-user")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(other)}")
    assert client.post(URL, payload, format="json").status_code == 403
    assert client.get(f"{URL}/{missing}/audit").status_code == 403


def test_audit_cursor_pages(client_manager, payload):
    client, _ = client_manager
    rule_id = client.post(URL, payload, format="json").data["id"]
    client.patch(f"{URL}/{rule_id}", {"expected_revision": 1, "name": "second"}, format="json")
    first = client.get(f"{URL}/{rule_id}/audit", {"limit": 1}).data
    second = client.get(f"{URL}/{rule_id}/audit", {"limit": 1, "cursor": first["next_cursor"]}).data
    assert first["items"][0]["revision"] == 2
    assert second["items"][0]["revision"] == 1
    assert second["next_cursor"] is None


def test_database_rejects_history_update_and_delete(client_manager, payload):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL trigger")
    client, _ = client_manager
    client.post(URL, payload, format="json")
    for operation in (lambda: RuleRevision.objects.update(after={}), lambda: RuleRevision.objects.all().delete()):
        with pytest.raises(DatabaseError), transaction.atomic():
            operation()
    assert RuleRevision.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_post_same_key_creates_one_rule(client_manager, payload):
    from django.db import close_old_connections

    _, user = client_manager
    token = str(AccessToken.for_user(user))
    key = str(uuid.uuid4())
    barrier = Barrier(2)

    def create():
        close_old_connections()
        try:
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            barrier.wait(timeout=15)
            response = client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
            return response.status_code, response.data["id"]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))
    assert results[0] == results[1]
    assert results[0][0] == 201
    assert RiskRule.objects.count() == RuleRevision.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_patch_allows_only_one_revision(client_manager, payload):
    from django.db import close_old_connections

    client, user = client_manager
    rule_id = client.post(URL, payload, format="json").data["id"]
    token = str(AccessToken.for_user(user))
    barrier = Barrier(2)

    def update(name):
        close_old_connections()
        try:
            concurrent_client = APIClient()
            concurrent_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            barrier.wait(timeout=15)
            return concurrent_client.patch(
                f"{URL}/{rule_id}", {"expected_revision": 1, "name": name}, format="json"
            ).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(update, ["first", "second"]))
    assert sorted(statuses) == [200, 409]
    rule = RiskRule.objects.get(pk=rule_id)
    assert rule.revision == 2
    assert rule.history.count() == 2
