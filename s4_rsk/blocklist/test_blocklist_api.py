import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, close_old_connections, transaction
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from assessments.models import DecisionType, TransferType
from rules.models import RiskRule

from .models import BlockedIdentifier, BlockedIdentifierCreateRequest
from .services import create_blocked_identifier, deactivate_blocked_identifier

URL = "/api/v1/blocked-identifiers"
VALID_IBAN_1 = "IR760990000000100324200001"
VALID_IBAN_2 = "IR760990000000100324200002"
VALID_IBAN_3 = "IR760990000000100324200003"
SOURCE_ACCOUNT_ID = "0192a7d1-0001-7000-8000-00000000a001"

pytestmark = pytest.mark.django_db


def _auth_client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def manager_client(django_user_model):
    user = django_user_model.objects.create_user("blocklist-manager")
    user.groups.add(Group.objects.get_or_create(name="manager")[0])
    return _auth_client(user), user


@pytest.fixture
def payload() -> dict:
    return {
        "kind": "IBAN",
        "value": VALID_IBAN_1,
        "reason": "Suspected mule account",
    }


def test_create_list_soft_delete_and_reblock_lifecycle(manager_client, payload):
    client, manager = manager_client

    created = client.post(URL, payload, format="json")
    assert created.status_code == 201
    entry_id = created.data["id"]
    assert created.data["kind"] == "IBAN"
    assert created.data["value"] == VALID_IBAN_1
    assert created.data["reason"] == payload["reason"]
    assert created.data["active"] is True
    assert created.data["created_by"] == manager.username
    assert created.data["deactivated_at"] is None
    assert created["X-Correlation-ID"]

    duplicate = client.post(URL, payload, format="json")
    assert duplicate.status_code == 409
    assert duplicate["Content-Type"] == "application/problem+json"
    assert duplicate.data["code"] == "CONFLICT"

    # Soft delete keeps the audit record and marks active=False
    deleted = client.delete(f"{URL}/{entry_id}")
    assert deleted.status_code == 204
    entry = BlockedIdentifier.objects.get(pk=entry_id)
    assert entry.active is False
    assert entry.deactivated_at is not None
    assert entry.deactivated_by_id == manager.pk

    first_deactivated_at = entry.deactivated_at
    deleted_again = client.delete(f"{URL}/{entry_id}")
    assert deleted_again.status_code == 204
    entry.refresh_from_db()
    assert entry.deactivated_at == first_deactivated_at

    # Filtering by active=true vs active=false
    active_list = client.get(URL, {"active": "true"})
    assert active_list.status_code == 200
    assert active_list.data["items"] == []

    inactive_list = client.get(URL, {"active": "false"})
    assert inactive_list.status_code == 200
    assert [item["id"] for item in inactive_list.data["items"]] == [entry_id]

    reblocked = client.post(URL, {**payload, "reason": "Re-blocked after repeat fraud"}, format="json")
    assert reblocked.status_code == 201
    assert reblocked.data["id"] != entry_id
    assert BlockedIdentifier.objects.filter(value=VALID_IBAN_1).count() == 2
    assert BlockedIdentifier.objects.filter(value=VALID_IBAN_1, active=True).count() == 1


def test_list_cursor_pagination_and_invalid_filters(manager_client):
    client, _ = manager_client
    ids = []
    for iban in (VALID_IBAN_1, VALID_IBAN_2, VALID_IBAN_3):
        res = client.post(URL, {"kind": "IBAN", "value": iban, "reason": f"Block {iban}"}, format="json")
        assert res.status_code == 201
        ids.append(res.data["id"])

    page1 = client.get(URL, {"limit": 2})
    assert page1.status_code == 200
    assert len(page1.data["items"]) == 2
    assert page1.data["next_cursor"] is not None

    page2 = client.get(URL, {"limit": 2, "cursor": page1.data["next_cursor"]})
    assert page2.status_code == 200
    assert len(page2.data["items"]) == 1
    assert page2.data["next_cursor"] is None

    seen_ids = [item["id"] for item in page1.data["items"]] + [item["id"] for item in page2.data["items"]]
    assert seen_ids == list(reversed(ids))

    bad_active = client.get(URL, {"active": "maybe"})
    assert bad_active.status_code == 400
    assert bad_active["Content-Type"] == "application/problem+json"
    assert bad_active.data["code"] == "VALIDATION_ERROR"

    bad_cursor = client.get(URL, {"cursor": "not-a-valid-cursor"})
    assert bad_cursor.status_code == 404
    assert bad_cursor["Content-Type"] == "application/problem+json"
    assert bad_cursor.data["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "bad_body",
    [
        {},
        {"kind": "ACCOUNT_ID", "value": VALID_IBAN_1, "reason": "Bad kind"},
        {"kind": "IBAN", "value": "US760990000000100324200001", "reason": "Non-Iranian IBAN"},
        {"kind": "IBAN", "value": "IR7609900000001003242000", "reason": "Too short"},
        {"kind": "IBAN", "value": f" {VALID_IBAN_1}", "reason": "Leading space"},
        {"kind": "IBAN", "value": 123456, "reason": "Numeric IBAN"},
        {"kind": "IBAN", "value": VALID_IBAN_1, "reason": ""},
        {"kind": "IBAN", "value": VALID_IBAN_1, "reason": "   "},
        {"kind": "IBAN", "value": VALID_IBAN_1, "reason": "x" * 256},
        {"kind": "IBAN", "value": VALID_IBAN_1, "reason": "Spoofed creator", "created_by": "admin"},
    ],
)
def test_invalid_payloads_are_rejected_without_side_effects(manager_client, bad_body):
    client, _ = manager_client
    response = client.post(URL, bad_body, format="json")
    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"
    assert response.data["code"] == "VALIDATION_ERROR"
    assert not BlockedIdentifier.objects.exists()


def test_idempotency_replay_conflict_cross_actor_and_invalid_first(manager_client, payload, django_user_model):
    client, _ = manager_client

    bad_key = client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY="not-a-uuid")
    assert bad_key.status_code == 400
    assert bad_key.data["code"] == "VALIDATION_ERROR"

    key = str(uuid.uuid4())
    assert client.post(URL, {}, format="json", HTTP_IDEMPOTENCY_KEY=key).status_code == 400
    assert not BlockedIdentifierCreateRequest.objects.exists()

    first = client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
    replay = client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert first.status_code == replay.status_code == 201
    assert first.data == replay.data
    assert BlockedIdentifier.objects.count() == 1

    diff_body = client.post(URL, {**payload, "reason": "Other reason"}, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert diff_body.status_code == 409
    assert diff_body.data["code"] == "IDEMPOTENCY_KEY_REUSED"

    other_manager = django_user_model.objects.create_user("other-blocklist-manager")
    other_manager.groups.add(Group.objects.get(name="manager"))
    cross_actor = _auth_client(other_manager).post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert cross_actor.status_code == 409
    assert cross_actor.data["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_auth_rbac_and_not_found(manager_client, payload, django_user_model):
    client, _ = manager_client
    missing_id = uuid.uuid4()

    not_found = client.delete(f"{URL}/{missing_id}")
    assert not_found.status_code == 404
    assert not_found["Content-Type"] == "application/problem+json"
    assert not_found.data["code"] == "NOT_FOUND"

    anon = APIClient()
    assert anon.get(URL).status_code == 401
    assert anon.post(URL, payload, format="json").status_code == 401
    assert anon.delete(f"{URL}/{missing_id}").status_code == 401

    operator = django_user_model.objects.create_user("regular-operator")
    op_client = _auth_client(operator)
    assert op_client.get(URL).status_code == 403
    assert op_client.post(URL, payload, format="json").status_code == 403
    assert op_client.delete(f"{URL}/{missing_id}").status_code == 403

    with pytest.raises(PermissionDenied):
        create_blocked_identifier(actor=operator, **payload)
    with pytest.raises(PermissionDenied):
        deactivate_blocked_identifier(actor=operator, identifier_id=missing_id)


def test_database_constraints_enforce_single_active_and_consistency(manager_client):
    _, manager = manager_client
    BlockedIdentifier.objects.create(
        kind=BlockedIdentifier.Kind.IBAN,
        value=VALID_IBAN_1,
        reason="First block",
        active=True,
        created_by=manager,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        BlockedIdentifier.objects.create(
            kind=BlockedIdentifier.Kind.IBAN,
            value=VALID_IBAN_1,
            reason="Duplicate active block",
            active=True,
            created_by=manager,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        BlockedIdentifier.objects.create(
            kind=BlockedIdentifier.Kind.IBAN,
            value=VALID_IBAN_2,
            reason="Inactive without timestamp",
            active=False,
            deactivated_at=None,
            created_by=manager,
        )


@pytest.mark.django_db(transaction=True)
def test_concurrent_post_same_key_creates_one_entry(manager_client, payload):
    _, user = manager_client
    token = str(AccessToken.for_user(user))
    key = str(uuid.uuid4())
    barrier = Barrier(2)

    def send():
        close_old_connections()
        try:
            concurrent_client = APIClient()
            concurrent_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            barrier.wait(timeout=15)
            response = concurrent_client.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
            return response.status_code, response.data["id"]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send(), range(2)))

    assert results[0] == results[1]
    assert results[0][0] == 201
    assert BlockedIdentifier.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_post_same_iban_without_shared_key_allows_only_one(manager_client, payload):
    _, user = manager_client
    token = str(AccessToken.for_user(user))
    barrier = Barrier(2)

    def send():
        close_old_connections()
        try:
            concurrent_client = APIClient()
            concurrent_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            barrier.wait(timeout=15)
            return concurrent_client.post(URL, payload, format="json").status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: send(), range(2)))

    assert sorted(statuses) == [201, 409]
    assert BlockedIdentifier.objects.filter(value=VALID_IBAN_1, active=True).count() == 1


def test_blocklist_entry_integrates_with_risk_assessment_engine(manager_client, django_user_model):
    """End-to-end US-05 + US-01B integration: blocking an IBAN rejects external transfers; soft-deleting allows them"""
    mgr_client, _ = manager_client

    RiskRule.objects.create(
        name="Global Registry Blocklist",
        type=RiskRule.Type.BLOCKLIST,
        parameters={},
        enabled=True,
    )

    pay_user = django_user_model.objects.create_user("s3-pay-blocklist-test")
    pay_user.groups.add(Group.objects.get_or_create(name="payment_service")[0])
    pay_client = _auth_client(pay_user)

    blocked = mgr_client.post(
        URL,
        {"kind": "IBAN", "value": VALID_IBAN_2, "reason": "Confirmed fraud destination"},
        format="json",
    )
    assert blocked.status_code == 201
    entry_id = blocked.data["id"]

    assessment_url = reverse("risk-assessment-create")
    rejected_res = pay_client.post(
        assessment_url,
        {
            "transaction_id": str(uuid.uuid4()),
            "transfer_type": TransferType.EXTERNAL,
            "source_account_id": SOURCE_ACCOUNT_ID,
            "destination_iban": VALID_IBAN_2,
            "amount": 1_500_000,
            "currency": "IRR",
            "occurred_at": "2026-10-24T10:00:00Z",
        },
        format="json",
    )
    assert rejected_res.status_code == 201
    assert rejected_res.data["decision"] == DecisionType.REJECT
    assert [r["code"] for r in rejected_res.data["reasons"]] == ["BLOCKLIST_MATCH"]

    assert mgr_client.delete(f"{URL}/{entry_id}").status_code == 204

    approved_res = pay_client.post(
        assessment_url,
        {
            "transaction_id": str(uuid.uuid4()),
            "transfer_type": TransferType.EXTERNAL,
            "source_account_id": SOURCE_ACCOUNT_ID,
            "destination_iban": VALID_IBAN_2,
            "amount": 1_500_000,
            "currency": "IRR",
            "occurred_at": "2026-10-24T10:05:00Z",
        },
        format="json",
    )
    assert approved_res.status_code == 201
    assert approved_res.data["decision"] == DecisionType.APPROVE
    assert [r["code"] for r in approved_res.data["reasons"]] == ["NO_RULE_MATCHED"]
