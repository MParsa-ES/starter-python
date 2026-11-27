import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from dashboard.selectors import count_open_review_items
from django.contrib.auth.models import Group
from django.db import IntegrityError, close_old_connections, transaction
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from assessments.models import DecisionEvent, DecisionType, EventType, TransferType
from common.openapi_contract import assert_payload_matches, assert_response_matches
from rules.models import RiskRule

from .models import ManualReviewItem, ReviewState

QUEUE_URL = "/api/v1/manual-review-queue"
SOURCE_ACCOUNT_ID = "0192a7d1-0001-7000-8000-00000000a001"
DEST_ACCOUNT_ID = "0192a7d1-0002-7000-8000-00000000a002"

pytestmark = pytest.mark.django_db


def _auth_client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def operator(django_user_model):
    user = django_user_model.objects.create_user("review-operator", password="test-password")
    user.groups.add(Group.objects.get_or_create(name="operator")[0])
    return user


@pytest.fixture
def second_operator(django_user_model):
    user = django_user_model.objects.create_user("review-operator-2", password="test-password")
    user.groups.add(Group.objects.get_or_create(name="operator")[0])
    return user


@pytest.fixture
def operator_client(operator) -> APIClient:
    return _auth_client(operator)


@pytest.fixture
def payment_client(django_user_model) -> APIClient:
    user = django_user_model.objects.create_user("s3-pay-review-test", password="test-password")
    user.groups.add(Group.objects.get_or_create(name="payment_service")[0])
    return _auth_client(user)


def _create_review_assessment(payment_client: APIClient, *, amount: int = 5_000_000) -> dict:
    RiskRule.objects.get_or_create(
        name="Review threshold",
        defaults={
            "type": RiskRule.Type.AMOUNT_LIMIT,
            "parameters": {"max_amount": 1_000_000, "decision": "REVIEW"},
            "enabled": True,
        },
    )
    response = payment_client.post(
        reverse("risk-assessment-create"),
        data={
            "transaction_id": str(uuid.uuid4()),
            "transfer_type": TransferType.INTERNAL,
            "source_account_id": SOURCE_ACCOUNT_ID,
            "destination_account_id": DEST_ACCOUNT_ID,
            "amount": amount,
            "currency": "IRR",
            "occurred_at": "2026-10-24T09:00:00Z",
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["decision"] == DecisionType.REVIEW
    return response.json()


def test_review_assessment_auto_enqueues_and_full_operator_lifecycle(
    payment_client, operator_client, operator
):
    assessment = _create_review_assessment(payment_client)
    assert count_open_review_items() == 1

    # 1. List OPEN queue
    list_resp = operator_client.get(QUEUE_URL, {"state": "OPEN"})
    assert list_resp.status_code == 200
    assert_response_matches(list_resp, path_template="/manual-review-queue", method="get")
    items = list_resp.json()["items"]
    assert len(items) == 1
    item_id = items[0]["item_id"]
    assert items[0]["decision_id"] == assessment["decision_id"]
    assert items[0]["transaction_id"] == assessment["transaction_id"]
    assert items[0]["state"] == ReviewState.OPEN
    assert items[0]["claimed_by"] is None

    # 2. Claim atomically
    claim_resp = operator_client.post(f"{QUEUE_URL}/{item_id}/claim")
    assert claim_resp.status_code == 200
    assert_response_matches(claim_resp, path_template="/manual-review-queue/{item_id}/claim", method="post")
    assert claim_resp.json()["state"] == ReviewState.CLAIMED
    assert claim_resp.json()["claimed_by"] == operator.username
    assert count_open_review_items() == 0

    # 3. Record final decision and append MANUAL_DECISION event
    decision_body = {"decision": "APPROVE", "reason": "Verified transfer with account owner"}
    assert_payload_matches("ReviewDecisionInput", decision_body)
    decide_resp = operator_client.post(
        f"{QUEUE_URL}/{item_id}/decision",
        data=decision_body,
        format="json",
        HTTP_X_CORRELATION_ID="manual-review-cid-1",
    )
    assert decide_resp.status_code == 200
    assert_response_matches(decide_resp, path_template="/manual-review-queue/{item_id}/decision", method="post")
    assert decide_resp.json()["state"] == ReviewState.DECIDED
    assert decide_resp.json()["claimed_by"] == operator.username

    events = list(DecisionEvent.objects.filter(assessment_id=assessment["decision_id"]).order_by("created_at"))
    assert len(events) == 2
    assert events[0].event_type == EventType.INITIAL_EVALUATION
    assert events[1].event_type == EventType.MANUAL_DECISION
    assert events[1].decision == DecisionType.APPROVE
    assert events[1].actor == operator.username
    assert events[1].reason_code == "MANUAL_APPROVE"
    assert events[1].reason_message == "Verified transfer with account owner"
    assert events[1].correlation_id == "manual-review-cid-1"


def test_approve_assessment_does_not_create_review_item(payment_client):
    resp = payment_client.post(
        reverse("risk-assessment-create"),
        data={
            "transaction_id": str(uuid.uuid4()),
            "transfer_type": TransferType.INTERNAL,
            "source_account_id": SOURCE_ACCOUNT_ID,
            "destination_account_id": DEST_ACCOUNT_ID,
            "amount": 500_000,
            "currency": "IRR",
            "occurred_at": "2026-10-24T09:00:00Z",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["decision"] == DecisionType.APPROVE
    assert ManualReviewItem.objects.count() == 0
    assert count_open_review_items() == 0


def test_state_transition_guards_and_claim_ownership(
    payment_client, operator_client, second_operator
):
    _create_review_assessment(payment_client)
    item = ManualReviewItem.objects.get()
    second_client = _auth_client(second_operator)

    # Cannot decide an OPEN item before claiming
    unclaimed = operator_client.post(
        f"{QUEUE_URL}/{item.item_id}/decision",
        data={"decision": "REJECT", "reason": "Premature decision"},
        format="json",
    )
    assert unclaimed.status_code == 409
    assert unclaimed.json()["code"] == "CONFLICT"

    # First operator claims
    assert operator_client.post(f"{QUEUE_URL}/{item.item_id}/claim").status_code == 200

    # Second operator cannot claim already claimed item
    double_claim = second_client.post(f"{QUEUE_URL}/{item.item_id}/claim")
    assert double_claim.status_code == 409
    assert double_claim.json()["code"] == "CONFLICT"

    # Second operator cannot decide an item claimed by another operator
    wrong_actor = second_client.post(
        f"{QUEUE_URL}/{item.item_id}/decision",
        data={"decision": "REJECT", "reason": "Wrong operator"},
        format="json",
    )
    assert wrong_actor.status_code == 403
    assert wrong_actor.json()["code"] == "FORBIDDEN"

    # First operator decides; subsequent decision returns 409
    assert (
        operator_client.post(
            f"{QUEUE_URL}/{item.item_id}/decision",
            data={"decision": "REJECT", "reason": "Confirmed fraud"},
            format="json",
        ).status_code
        == 200
    )
    decided_again = operator_client.post(
        f"{QUEUE_URL}/{item.item_id}/decision",
        data={"decision": "APPROVE", "reason": "Too late"},
        format="json",
    )
    assert decided_again.status_code == 409
    assert decided_again.json()["code"] == "CONFLICT"


def test_idempotency_for_claim_and_decision(payment_client, operator_client):
    _create_review_assessment(payment_client)
    item = ManualReviewItem.objects.get()

    claim_key = str(uuid.uuid4())
    first_claim = operator_client.post(f"{QUEUE_URL}/{item.item_id}/claim", HTTP_IDEMPOTENCY_KEY=claim_key)
    replay_claim = operator_client.post(f"{QUEUE_URL}/{item.item_id}/claim", HTTP_IDEMPOTENCY_KEY=claim_key)
    assert first_claim.status_code == replay_claim.status_code == 200
    assert first_claim.json() == replay_claim.json()

    # Reusing claim key on decision endpoint -> 409 IDEMPOTENCY_KEY_REUSED
    reused = operator_client.post(
        f"{QUEUE_URL}/{item.item_id}/decision",
        data={"decision": "APPROVE", "reason": "Trying to reuse claim key"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=claim_key,
    )
    assert reused.status_code == 409
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    decide_key = str(uuid.uuid4())
    body = {"decision": "REJECT", "reason": "Fraud pattern"}
    first_dec = operator_client.post(
        f"{QUEUE_URL}/{item.item_id}/decision", data=body, format="json", HTTP_IDEMPOTENCY_KEY=decide_key
    )
    replay_dec = operator_client.post(
        f"{QUEUE_URL}/{item.item_id}/decision", data=body, format="json", HTTP_IDEMPOTENCY_KEY=decide_key
    )
    assert first_dec.status_code == replay_dec.status_code == 200
    assert first_dec.json() == replay_dec.json()
    assert DecisionEvent.objects.filter(event_type=EventType.MANUAL_DECISION).count() == 1

    conflict_dec = operator_client.post(
        f"{QUEUE_URL}/{item.item_id}/decision",
        data={"decision": "APPROVE", "reason": "Different body"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=decide_key,
    )
    assert conflict_dec.status_code == 409
    assert conflict_dec.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_validation_rbac_pagination_and_404(payment_client, operator_client, django_user_model):
    # Create 3 review items for cursor pagination
    for _ in range(3):
        _create_review_assessment(payment_client)

    page1 = operator_client.get(QUEUE_URL, {"limit": 2})
    assert page1.status_code == 200
    assert len(page1.json()["items"]) == 2
    assert page1.json()["next_cursor"] is not None

    page2 = operator_client.get(QUEUE_URL, {"limit": 2, "cursor": page1.json()["next_cursor"]})
    assert page2.status_code == 200
    assert len(page2.json()["items"]) == 1
    assert page2.json()["next_cursor"] is None

    # Invalid state filter -> 400
    bad_state = operator_client.get(QUEUE_URL, {"state": "UNKNOWN"})
    assert bad_state.status_code == 400
    assert bad_state.json()["code"] == "VALIDATION_ERROR"

    # Invalid decision payloads -> 400
    item = ManualReviewItem.objects.first()
    operator_client.post(f"{QUEUE_URL}/{item.item_id}/claim")
    for bad_payload in (
        {"decision": "REVIEW", "reason": "Cannot decide REVIEW"},
        {"decision": "APPROVE", "reason": "   "},
        {"decision": "APPROVE", "reason": "ok", "extra": "nope"},
    ):
        resp = operator_client.post(f"{QUEUE_URL}/{item.item_id}/decision", data=bad_payload, format="json")
        assert resp.status_code == 400

    # Unknown item_id -> 404
    missing = uuid.uuid4()
    assert operator_client.post(f"{QUEUE_URL}/{missing}/claim").status_code == 404
    assert (
        operator_client.post(
            f"{QUEUE_URL}/{missing}/decision",
            data={"decision": "APPROVE", "reason": "Missing"},
            format="json",
        ).status_code
        == 404
    )

    # Auth: anonymous -> 401, non-operator (manager) -> 403
    assert APIClient().get(QUEUE_URL).status_code == 401
    manager = django_user_model.objects.create_user("non-op-manager", password="pw")
    manager.groups.add(Group.objects.get_or_create(name="manager")[0])
    mgr_client = _auth_client(manager)
    assert mgr_client.get(QUEUE_URL).status_code == 403
    assert mgr_client.post(f"{QUEUE_URL}/{item.item_id}/claim").status_code == 403


def test_database_constraint_rejects_claimed_without_operator(payment_client):
    _create_review_assessment(payment_client)
    item = ManualReviewItem.objects.get()
    with pytest.raises(IntegrityError), transaction.atomic():
        ManualReviewItem.objects.filter(pk=item.pk).update(state=ReviewState.CLAIMED, claimed_by=None)


@pytest.mark.django_db(transaction=True)
def test_concurrent_claim_allows_only_one_operator(payment_client, operator, second_operator):
    _create_review_assessment(payment_client)
    item = ManualReviewItem.objects.get()
    tokens = [str(AccessToken.for_user(operator)), str(AccessToken.for_user(second_operator))]
    barrier = Barrier(2)

    def attempt_claim(token: str) -> int:
        close_old_connections()
        try:
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            barrier.wait(timeout=15)
            return client.post(f"{QUEUE_URL}/{item.item_id}/claim").status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(attempt_claim, tokens))

    assert sorted(statuses) == [200, 409]
    item.refresh_from_db()
    assert item.state == ReviewState.CLAIMED
    assert item.claimed_by_id in {operator.pk, second_operator.pk}
