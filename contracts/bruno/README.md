# Manual acceptance requests

Open this folder as a Bruno collection, select Local, and set local secret
variables `managerSessionId` and `nonManagerSessionId` from your own development
accounts. Never save actual cookie values in tracked files. Seed the development
rules explicitly using the steps in `docs/us-02a-risk-rules.md`.

Disable automatic cookie-jar sending for the anonymous request; otherwise a
previous manager cookie could authenticate it. The non-manager account must be
logged in but must not belong to manager. Run success and forbidden requests
independently and retain actual results/screenshots as review evidence.

These files are request definitions; their presence alone is not evidence of
a completed manual Bruno run. Equivalent session/permission paths are covered
by the automated PostgreSQL integration suite.
