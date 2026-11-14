"""Consumer contract tests: our expectations against a RUNNING provider.

Target: NEIGHBOR_BASE_URL - either a Prism mock built from the neighbour's contract
(http://127.0.0.1:4010) or the neighbour's real service (bonus, section 12).

    prism mock openapi/neighbors/s2_ldg.yaml -p 4010
    $env:NEIGHBOR_BASE_URL="http://127.0.0.1:4010"
    pytest -m contract --run-neighbor-contract -v -s

Optional: NEIGHBOR_ACCOUNT_ID_OK / NEIGHBOR_ACCOUNT_ID_MISSING select the seeded account ids.
"""

import os
from datetime import UTC, datetime

import httpx
import pytest

from common.openapi_contract import NEIGHBOR_SPEC, assert_response_matches

from .ledger_client import STATUS_ACCOUNT_NOT_FOUND, STATUS_OK, LedgerClient, assess_ledger_history

BASE_URL = os.environ.get("NEIGHBOR_BASE_URL", "").rstrip("/")
ACCOUNT_OK = os.environ.get("NEIGHBOR_ACCOUNT_ID_OK", "0192f5a0-5555-7aaa-8bbb-0123456789ab")
ACCOUNT_MISSING = os.environ.get("NEIGHBOR_ACCOUNT_ID_MISSING", "0192f5a0-9999-7aaa-8bbb-000000000000")
SINCE = datetime(2026, 10, 24, tzinfo=UTC)
PATH = "/api/v1/accounts/{account_id}/entries"

pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(not BASE_URL, reason="NEIGHBOR_BASE_URL is not set"),
]


def stamp(message: str) -> None:
    print(f"[{datetime.now(UTC).isoformat(timespec='milliseconds')}] {message}")


def _get(account_id: str, **extra_headers) -> httpx.Response:
    url = f"{BASE_URL}/api/v1/accounts/{account_id}/entries"
    stamp(f"GET {url}")
    response = httpx.get(url, params={"direction": "DEBIT"}, headers=extra_headers, timeout=5.0)
    stamp(f"-> {response.status_code} {response.headers.get('content-type')}")
    return response


def test_success_response_matches_neighbor_contract():
    response = _get(ACCOUNT_OK)
    assert response.status_code == 200
    assert_response_matches(response, path_template=PATH, method="get", spec_path=NEIGHBOR_SPEC)


def test_unknown_account_response_matches_neighbor_contract():
    # "Prefer: code=404" makes a Prism mock return its 404 example; a real provider ignores it.
    response = _get(ACCOUNT_MISSING, Prefer="code=404")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert_response_matches(response, path_template=PATH, method="get", spec_path=NEIGHBOR_SPEC)


def test_our_client_understands_the_real_success_response():
    stamp("LedgerClient.recent_debits against the running neighbour")
    history = assess_ledger_history(LedgerClient(BASE_URL), ACCOUNT_OK, SINCE)
    stamp(f"-> status={history.status} entries={len(history.entries)}")
    assert history.status == STATUS_OK
    assert history.status != STATUS_ACCOUNT_NOT_FOUND
