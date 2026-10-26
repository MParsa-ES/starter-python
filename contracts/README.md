# API contract

Export the OpenAPI 3.1 contract from the Django implementation after changing
serializers, permissions or response shapes:

```powershell
cd s4_rsk
..\.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file ../contracts/openapi.yaml
```

Commit `openapi.yaml` with the implementation. Error responses use
`application/problem+json`. Human authentication is described in ADR-001.
