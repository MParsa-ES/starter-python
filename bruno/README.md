# Manual acceptance requests

Open this folder as a Bruno collection, select Local, and set local secret
variables `managerAccessToken` and `nonManagerAccessToken` from your own development
accounts using the JWT guide. Never save actual token values in tracked files. Seed the development
rules explicitly using the steps in `docs/us-02a-risk-rules.md`.

The anonymous request sends no bearer token. The non-manager account must not
belong to manager. Run success and forbidden requests
independently and retain actual results/screenshots as review evidence.

These files are request definitions; their presence alone is not evidence of
a completed manual Bruno run. JWT and permission paths are covered
by the automated PostgreSQL integration suite.
