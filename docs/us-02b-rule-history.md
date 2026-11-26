# US-02B: Rule revision history

Manager-only POST, PATCH and audit endpoints use the transactional services in `rules.services`. They validate rule parameters, lock the rule during updates, reject stale revisions and record the actor and before/after snapshots atomically. Existing rules do not receive fabricated history: their first service update records the previous and new state. The `AMOUNT_LIMIT` parameter is `max_amount` and must be an integer between 1 and the signed 64-bit maximum. `BLOCKLIST` currently accepts any object; more specific semantics need team agreement.

The PostgreSQL migration rejects ordinary UPDATE and DELETE statements on history rows. It does not restrict TRUNCATE or a database owner who disables the trigger. Direct ORM, bulk and SQL writes to `RiskRule` bypass service validation and history; production deployment needs separate, restricted database roles and an agreed way to enforce the service boundary. Database-owner privileges are not an audit protection boundary.

The amount is expressed in IRR. Migration 0005 renames the legacy `max_amount_irr` key in current AMOUNT_LIMIT rules, retaining other parameters. If both keys exist with conflicting values, the migration stops for manual resolution. History snapshots and stored idempotent responses are intentionally not rewritten, so historical responses may still contain the old key. New requests must use `max_amount`. This data migration does not reverse the rename when rolled back.

See [API testing](reports/us-02-api-testing.md) and the [test matrix](test-matrices/us-02.md). Run tests from `s4_rsk`, or from the repository root with `python -m pytest -c s4_rsk/pytest.ini s4_rsk`; after new migrations, `--create-db` recreates the **test database**. Use a dedicated PostgreSQL instance and preserve important data. The subprocess test sets its working directory to `s4_rsk` so its relative `manage.py` path works from either directory.

## RSK-31 progress

- Optional `max_daily_amount` and `max_daily_count` must be positive signed 64-bit integers; a configured `decision` must be `REVIEW` or `REJECT`.
- When an enabled daily limit cannot be evaluated because no ledger client is configured, the engine returns `REVIEW` with `LEDGER_UNAVAILABLE` instead of silently approving it. The existing assessment API exposes the reason and rule snapshot to consumers.
- The `/rules` frontend supports manager token authentication, listing and pagination, creating and editing rules with optimistic revision checks, and paginated audit history. The token remains in component memory. Production nginx proxies `/api/` to the backend. Integers outside JavaScript's safe range cannot be edited through this UI; use the API instead.
- PostgreSQL-backed tests exercise management and assessment integration; frontend component tests cover editing, validation, and API errors. The ledger service must be configured for daily limits; its provider contract and deployment credentials remain a cross-team dependency.
