"""Consumer tests: S4-RSK's ledger client against a Stub of S2-LDG (no neighbour needed).

The stub answers are taken from the examples of the neighbour's OpenAPI file
(openapi/neighbors/s2_ldg.yaml), so the tests stay tied to the draft contract.
The asserts check the behaviour of OUR code (decision signal), not only that the stub was called.
"""

import uuid
from datetime import UTC, datetime

import httpx
import pytest

from common.openapi_contract import NEIGHBOR_SPEC, contract_example, load_spec

from .ledger_client import (
    STATUS_ACCOUNT_NOT_FOUND,
    STATUS_LEDGER_UNAVAILABLE,
    STATUS_OK,
    LedgerClient,
    LedgerError,
    assess_ledger_history,
    resolve_base_url,
)

PATH = "/api/v1/accounts/{account_id}/entries"
SPEC = load_spec(NEIGHBOR_SPEC)
OK_BODY = contract_example(SPEC, PATH, "get", "200")
NOT_FOUND_BODY = contract_example(SPEC, PATH, "get", "404")
UNAVAILABLE_BODY = contract_example(SPEC, PATH, "get", "503")

ACCOUNT_ID = uuid.UUID("0192f5a0-5555-7aaa-8bbb-0123456789ab")
SINCE = datetime(2026, 10, 24, 0, 0, tzinfo=UTC)


def _client(handler, base_url="http://s2-ldg.test"):
    return LedgerClient(base_url, transport=httpx.MockTransport(handler))


def test_success_returns_parsed_debits_and_sends_the_draft_request():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        seen["correlation"] = request.headers.get("X-Correlation-ID")
        return httpx.Response(200, json=OK_BODY)

    history = assess_ledger_history(_client(handler), ACCOUNT_ID, SINCE, correlation_id="stub-cid-1")

    assert seen["path"] == f"/api/v1/accounts/{ACCOUNT_ID}/entries"
    assert seen["params"]["direction"] == "DEBIT"
    assert seen["params"]["from"] == "2026-10-24T00:00:00+00:00"
    assert seen["correlation"] == "stub-cid-1"
    assert history.status == STATUS_OK
    assert history.forced_decision is None
    assert [entry.amount for entry in history.entries] == [1_500_000, 700_000]
    assert all(entry.occurred_at.tzinfo is not None for entry in history.entries)


def test_pagination_follows_next_cursor_until_exhausted():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params.get("cursor"))
        if request.url.params.get("cursor") is None:
            return httpx.Response(200, json={"items": OK_BODY["items"][:1], "next_cursor": "page-2"})
        return httpx.Response(200, json={"items": OK_BODY["items"][1:], "next_cursor": None})

    entries = _client(handler).recent_debits(ACCOUNT_ID, SINCE)

    assert calls == [None, "page-2"]
    assert len(entries) == 2


def test_unknown_account_forces_review_with_explicit_reason():
    def handler(request):
        return httpx.Response(404, json=NOT_FOUND_BODY, headers={"Content-Type": "application/problem+json"})

    history = assess_ledger_history(_client(handler), ACCOUNT_ID, SINCE)

    assert history.reason_code == STATUS_ACCOUNT_NOT_FOUND
    assert history.forced_decision == "REVIEW"
    assert history.entries == ()


def test_timeout_forces_review_instead_of_raising():
    def handler(request):
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    history = assess_ledger_history(_client(handler), ACCOUNT_ID, SINCE)

    assert history.reason_code == STATUS_LEDGER_UNAVAILABLE
    assert history.forced_decision == "REVIEW"


def test_server_error_forces_review():
    def handler(request):
        return httpx.Response(503, json=UNAVAILABLE_BODY, headers={"Content-Type": "application/problem+json"})

    history = assess_ledger_history(_client(handler), ACCOUNT_ID, SINCE)

    assert history.reason_code == STATUS_LEDGER_UNAVAILABLE
    assert history.forced_decision == "REVIEW"


def test_malformed_success_body_is_not_trusted():
    bad_entry = {"id": "x", "account_id": "y", "direction": "DEBIT", "occurred_at": "2026-10-24T08:00:00Z"}

    def handler(request):
        return httpx.Response(200, json={"items": [bad_entry], "next_cursor": None})

    with pytest.raises(LedgerError):
        _client(handler).recent_debits(ACCOUNT_ID, SINCE)
    assert assess_ledger_history(_client(handler), ACCOUNT_ID, SINCE).forced_decision == "REVIEW"


@pytest.mark.parametrize("body", [{"items": None}, {"items": [] , "next_cursor": 1}, {"items": [None]}])
def test_malformed_page_is_reported_as_unavailable(body):
    def handler(request):
        return httpx.Response(200, json=body)

    history = assess_ledger_history(_client(handler), ACCOUNT_ID, SINCE)
    assert history.reason_code == STATUS_LEDGER_UNAVAILABLE
    assert history.forced_decision == "REVIEW"


def test_entry_for_another_account_is_rejected():
    entry = {**OK_BODY["items"][0], "account_id": "0192f5a0-9999-7aaa-8bbb-000000000000"}

    def handler(request):
        return httpx.Response(200, json={"items": [entry], "next_cursor": None})

    assert assess_ledger_history(_client(handler), ACCOUNT_ID, SINCE).reason_code == STATUS_LEDGER_UNAVAILABLE


def test_neighbor_base_url_environment_variable_selects_the_host(monkeypatch):
    monkeypatch.setenv("NEIGHBOR_BASE_URL", "http://neighbour.invalid:9999/")
    hosts = []

    def handler(request):
        hosts.append((request.url.host, request.url.port))
        return httpx.Response(200, json=OK_BODY)

    LedgerClient(transport=httpx.MockTransport(handler)).recent_debits(ACCOUNT_ID, SINCE)

    assert hosts == [("neighbour.invalid", 9999)]


def test_missing_neighbor_base_url_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("NEIGHBOR_BASE_URL", raising=False)
    monkeypatch.delenv("S2_LDG_BASE_URL", raising=False)
    with pytest.raises(LedgerError, match="NEIGHBOR_BASE_URL"):
        resolve_base_url()


def test_unexpected_client_error_is_not_treated_as_empty_history():
    def handler(request):
        return httpx.Response(403, json={"code": "FORBIDDEN"})

    with pytest.raises(LedgerError, match="403"):
        _client(handler).recent_debits(ACCOUNT_ID, SINCE)
    assert assess_ledger_history(_client(handler), ACCOUNT_ID, SINCE).forced_decision == "REVIEW"


def test_endless_cursor_chain_is_cut_off():
    def handler(request):
        return httpx.Response(200, json={"items": [], "next_cursor": "again"})

    with pytest.raises(LedgerError, match="too many pages"):
        _client(handler).recent_debits(ACCOUNT_ID, SINCE)


def test_bearer_token_is_sent_when_configured():
    seen = {}

    def handler(request):
        seen["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json=OK_BODY)

    client = LedgerClient("http://s2-ldg.test", transport=httpx.MockTransport(handler), token="stub-token")
    client.recent_debits(ACCOUNT_ID, SINCE)

    assert seen["authorization"] == "Bearer stub-token"
