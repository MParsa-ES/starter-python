# US-02A: Read risk-rule configuration

Owner: Ali. Reviewer: Abolfazl. US-02A is a plan identifier, not a Jira key.

`GET /api/v1/risk-rules?limit=50&cursor=...` reads PostgreSQL records. It requires
an active session user in the exact `manager` group. Anonymous/inactive sessions
return 403 `UNAUTHORIZED`; authenticated users without that role return 403
`FORBIDDEN`. Session behavior and pending S3 auth are documented in ADR-001.

The response is `{ "items": [...], "next_cursor": null }`. Follow the opaque
`next_cursor` using the same limit until null. The default page size is 50 and
the maximum is 200. Invalid cursors return 404 Problem Details. Each item has
`id` (UUIDv7), `name`, `type`, `parameters`, `enabled`, `effective_at`, `revision`,
`created_at`, and `updated_at`. Times use UTC. Disabled/future rules are included:
this is configuration visibility, not a claim that the engine applies them.

Initial types are AMOUNT_LIMIT and BLOCKLIST; positive revisions and known types
have database constraints. No POST/PATCH, engine, audit editing or automatic
seed is included. Parameter write validation/revision updates belong to US-02B.
The example amount threshold is a development illustration, not an approved
bank policy. The seed records are disabled deliberately.

After migrating a **development database**, opt in to the fixture:

```powershell
.\.venv\Scripts\python.exe s4_rsk/manage.py migrate
.\.venv\Scripts\python.exe s4_rsk/manage.py loaddata dev_risk_rules
```

Do not load fixtures into shared/production databases. Loading this fixture
again resets its two fixed development records. No account/password is seeded.
For Swagger, create an interactive staff account and explicitly assign manager
as described in the README. Copy that account's session cookie only into local
Bruno variables, never into tracked collection files.

Independent acceptance: migrate, load the fixture, log in, list two records,
then verify forbidden/anonymous requests and follow a one-item cursor page.
After stopping and restarting only the application process, the same records
must remain. Swagger is `/api/docs/`; Bruno files are in `contracts/bruno`.
