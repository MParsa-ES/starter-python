"""Consumer client for the S2-LDG ledger service (our neighbour / provider).

While assessing a transfer, S4-RSK reads the recent DEBIT entries of the source
account to spot unusual withdrawal patterns. Failures of the neighbour must never
break our own endpoint: they are translated into a safe REVIEW signal.

The neighbour's address is read from ``NEIGHBOR_BASE_URL`` (see ``resolve_base_url``);
``S2_LDG_BASE_URL`` from .env is the fallback.

Status of the integration: this module is the tested client. It is not yet called by
``assessments.services`` (that wiring belongs to US-01B).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote
from uuid import UUID

import httpx

DEFAULT_TIMEOUT_SECONDS = 2.0
MAX_PAGES = 10
ENTRIES_PATH = "/api/v1/accounts/{account_id}/entries"

STATUS_OK = "OK"
STATUS_ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
STATUS_LEDGER_UNAVAILABLE = "LEDGER_UNAVAILABLE"


class LedgerError(Exception):
    """The ledger answer cannot be used."""


class LedgerAccountNotFound(LedgerError):
    """S2-LDG answered 404 for the account."""


class LedgerUnavailable(LedgerError):
    """Timeout, connection failure or 5xx from S2-LDG."""


@dataclass(frozen=True)
class LedgerEntry:
    id: str
    account_id: str
    direction: str
    amount: int
    occurred_at: datetime


@dataclass(frozen=True)
class LedgerHistory:
    """What the rule engine receives; ``forced_decision`` is set when history is unusable."""

    status: str
    entries: tuple[LedgerEntry, ...] = ()
    forced_decision: str | None = None

    @property
    def reason_code(self) -> str | None:
        return None if self.status == STATUS_OK else self.status


def resolve_base_url(explicit: str | None = None) -> str:
    """NEIGHBOR_BASE_URL is the single place where the neighbour address is read."""
    url = explicit or os.environ.get("NEIGHBOR_BASE_URL") or os.environ.get("S2_LDG_BASE_URL")
    if not url:
        raise LedgerError("NEIGHBOR_BASE_URL is not configured.")
    return url.rstrip("/")


def _parse_entry(raw: dict) -> LedgerEntry:
    try:
        if not isinstance(raw, dict):
            raise ValueError("entry must be an object")
        amount = raw["amount"]
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
            raise ValueError("amount must be a positive integer")
        if raw["direction"] != "DEBIT":
            raise ValueError("entry must be a debit")
        UUID(str(raw["id"]))
        UUID(str(raw["account_id"]))
        occurred_at = datetime.fromisoformat(raw["occurred_at"])
        if occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return LedgerEntry(
            id=str(raw["id"]),
            account_id=str(raw["account_id"]),
            direction=str(raw["direction"]),
            amount=amount,
            occurred_at=occurred_at,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LedgerError(f"Malformed ledger entry: {exc}") from exc


class LedgerClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
        token: str | None = None,
    ):
        self._base_url = resolve_base_url(base_url)
        self._timeout = timeout
        self._transport = transport
        self._token = token

    def recent_debits(self, account_id, since: datetime, *, correlation_id: str | None = None) -> list[LedgerEntry]:
        headers = {"Accept": "application/json"}
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        url = ENTRIES_PATH.format(account_id=quote(str(account_id), safe=""))
        entries: list[LedgerEntry] = []
        cursor: str | None = None

        with httpx.Client(base_url=self._base_url, timeout=self._timeout, transport=self._transport) as http:
            for _ in range(MAX_PAGES):
                params = {"direction": "DEBIT", "from": since.isoformat(), "limit": 200}
                if cursor:
                    params["cursor"] = cursor
                try:
                    response = http.get(url, params=params, headers=headers)
                except httpx.HTTPError as exc:  # timeout, connection refused, protocol error
                    raise LedgerUnavailable(f"Ledger request failed: {type(exc).__name__}") from exc

                if response.status_code == 404:
                    raise LedgerAccountNotFound(str(account_id))
                if response.status_code >= 500:
                    raise LedgerUnavailable(f"Ledger answered {response.status_code}")
                if response.status_code != 200:
                    raise LedgerError(f"Unexpected ledger status {response.status_code}")
                try:
                    body = response.json()
                    items = body["items"]
                    cursor = body.get("next_cursor")
                    if not isinstance(items, list) or (cursor is not None and not isinstance(cursor, str)):
                        raise ValueError("invalid page")
                except (ValueError, KeyError, TypeError) as exc:
                    raise LedgerError("Ledger answered 200 with an unreadable body") from exc
                for item in items:
                    entry = _parse_entry(item)
                    if entry.account_id != str(account_id):
                        raise LedgerError("Ledger returned an entry for a different account")
                    entries.append(entry)
                if not cursor:
                    return entries
        raise LedgerError("Ledger returned too many pages")


def assess_ledger_history(
    client: LedgerClient, account_id, since: datetime, *, correlation_id: str | None = None
) -> LedgerHistory:
    """Never raises: turns every neighbour failure into an explicit REVIEW signal."""
    try:
        entries = client.recent_debits(account_id, since, correlation_id=correlation_id)
    except LedgerAccountNotFound:
        return LedgerHistory(STATUS_ACCOUNT_NOT_FOUND, forced_decision="REVIEW")
    except LedgerError:
        return LedgerHistory(STATUS_LEDGER_UNAVAILABLE, forced_decision="REVIEW")
    return LedgerHistory(STATUS_OK, tuple(entries))
