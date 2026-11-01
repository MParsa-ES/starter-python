# LabBank S4-RSK

The official service is **Django + Django REST Framework on port 8084**, backed
by PostgreSQL. `main.py` is the historical Session 01 FastAPI exercise; it is
preserved as course evidence and is not the service entry point. Do not use
`uvicorn main:app` to run S4-RSK.

## First run (PowerShell, repository root)

Requirements: Python 3.12, Docker Desktop with Linux containers, Git.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item s4_rsk/.env.example s4_rsk/.env
docker compose up -d s4-rsk-db
.\.venv\Scripts\python.exe s4_rsk/manage.py migrate
.\.venv\Scripts\python.exe s4_rsk/manage.py runserver 127.0.0.1:8084
```

Copy the env template only on first setup; preserve an existing local `.env`.
For macOS/Linux use `python3.12 -m venv .venv`, `cp` and `.venv/bin/python`.
The template credentials are for local development only. Never commit `.env`.

Both Compose services read `s4_rsk/.env`, so database name, user and password
come from the same file. Host Django uses `localhost:5434`; container Django
overrides only the network address to `s4-rsk-db:5432`. Keep the sample host
port at 5434. Do not rely on a root `.env` to configure the database.

If a pre-existing volume was initialized with different credentials, changing
the env file does not rename its existing PostgreSQL role. Preserve that data
and use matching credentials or arrange a deliberate database migration.

## Run the complete backend in Docker

```powershell
docker compose up --build -d
docker compose ps
```

The entrypoint applies migrations then starts Gunicorn on 8084. Do not run the
host server and container server on the same port at the same time. Stop with
`docker compose stop`; restart with `docker compose start`. Do not use
`docker compose down -v` when you need to preserve the database.

## Verify and explore

```powershell
curl.exe -i http://127.0.0.1:8084/health
curl.exe -i http://127.0.0.1:8084/ready
.\.venv\Scripts\python.exe scripts/verify_health.py
```

`GET /health` returns `200 {"status":"UP","service":"s4-rsk"}` without querying
the database. `/ready` queries PostgreSQL and returns
`200 {"status":"READY","service":"s4-rsk","database":"CONNECTED"}` or
503 `application/problem+json`. Both probes are public. Responses include
`X-Correlation-ID`. Swagger is `/api/docs/`; schema is `/api/schema/`.

## Authentication baseline

Management endpoints use Django sessions. Unsafe authenticated requests must
include the CSRF cookie and `X-CSRFToken`. The `manager`, `operator` and
`analyst` roles are Django groups; the initial rule list requires `manager`.
The staff flag grants no API role by itself. See
[ADR-001](docs/adr/ADR-001-authentication.md) for the exact 403 problem codes,
same-origin UI contract and pending S3 authentication decision.

For local Swagger use, create an interactive account with
`python s4_rsk/manage.py createsuperuser`, log into `/admin/login/`, create the
`manager` group and explicitly assign it to that account. Do not store real
passwords in fixtures or request collections. Production requires `DEBUG=False`,
a non-development `SECRET_KEY`, HTTPS, correct `ALLOWED_HOSTS` and secure cookies.

## Tests and schema validation

Use a dedicated test database/server; pytest creates a `test_` database and
requires a PostgreSQL role with CREATEDB. Never point it at shared data.

```powershell
$env:POSTGRES_DB = 's4_rsk_test'
$env:POSTGRES_USER = 's4_rsk_user'
$env:POSTGRES_PASSWORD = 's4_rsk_password'
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '15434'
$env:DEBUG = 'True'
docker run -d --name s4-rsk-ali-test-db -e POSTGRES_DB=s4_rsk_test -e POSTGRES_USER=s4_rsk_user -e POSTGRES_PASSWORD=s4_rsk_password -p 127.0.0.1:15434:5432 --tmpfs /var/lib/postgresql/data postgres:16-alpine
Set-Location s4_rsk
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file ../contracts/openapi.yaml
..\.venv\Scripts\ruff.exe check .
```

If that test container already exists, start it rather than running `docker run`
again. The tmpfs database is disposable and does not use the project's data
volume. Remove the test-only environment overrides or open a fresh terminal
before returning to the development service.

Frontend scaffolding and persistent idempotency remain separate work items;
their existence is not implied by this backend baseline.
