# ADR-001: Initial management API authentication

Status: implemented baseline for review; service-to-service authentication pending.

The management API uses Django sessions and DRF SessionAuthentication. Unsafe
requests from authenticated clients require Django's CSRF cookie and
`X-CSRFToken`; no CSRF exemption is introduced. Deploy the UI and API behind
one origin (a Vite proxy may be used locally). Production uses HTTPS and secure
session/CSRF cookies. Never derive roles or actor IDs from request body fields.

All API views require authentication by default. `/health` and `/ready` are
explicitly public and do not attempt session authentication. Schema and Swagger
remain public for the lab; they contain no application records or credentials.

The exact group names are `manager`, `operator`, and `analyst`. Membership is
assigned by an administrator, never by client input. Only `manager` may read
the risk-rule configuration in US-02A. Staff/superuser flags alone do not grant
this role. No operator/analyst domain access is implemented until those endpoints
exist. SessionAuthentication returns **403** for missing/invalid sessions as
well as insufficient role; clients distinguish the problem `code`:
`UNAUTHORIZED` versus `FORBIDDEN`. A future bearer adapter must document its 401
and WWW-Authenticate behavior separately.

For the initial lab workflow, a manager who also has Django's separate staff
permission can log in through `/admin/login/` on the same origin, then use
Swagger. Do not expose a password/token in a fixture, Bruno file, or repository.
An interactive account is created with `manage.py createsuperuser`; explicitly
assign its `manager` group using Django admin. An account without that group is
deliberately denied even if it is a superuser.

The S3 service credential scheme is not agreed yet. Do not treat these human
sessions as service authentication and do not trust arbitrary identity headers.
Before exposing assessment/callback endpoints, agree on an adapter with S3,
credential verification, scope and rotation. PREP-08 is only partially addressed
by this management baseline, not complete service integration.
