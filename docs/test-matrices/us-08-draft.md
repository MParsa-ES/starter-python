# Draft US-08 test matrix: decision explainability

This draft is not the final story specification. The current `DecisionReason` model includes code, message, rule_id, rule_revision, and rule_snapshot; the model alone does not prove the API or story is complete. The endpoint, permitted roles, response contract, number of reasons, and handling of sensitive data require team agreement.

## RSK-37: initial work

The tests in `assessments/test_explanation_serialization.py` cover the existing representation of a reason with its rule ID, revision, and snapshot, as well as a default reason without a rule. These tests were the starting point; the API and limitations of the newer implementation are described below.

## Proposed RSK-37 implementation

`GET /api/v1/risk-assessments/{decision_id}/reasons` returns recorded reasons in creation order with `limit` and `cursor` for active `manager`, `operator`, and `analyst` roles. Each reason includes `code`, `message`, `rule_id`, and `rule_revision`. This endpoint does not expose rule parameters or snapshots. It does display the recorded message, whose content policy requires confirmation during the team's security review. An unknown ID returns 404; unauthorized access returns 401 or 403. The `/explanations` page uses this API. The roles and omission of snapshots follow the current history pattern and are implementation choices that require team review. Use the US-06 API for manual decision history; this endpoint shows initial assessment reasons.

| ID | Proposed scenario | Input / conditions | Proposed result; requires agreement | Proposed level |
|---|---|---|---|---|
| R08-01 | Decision reason from a matching rule | Decision with one matching rule | Display code, message, and associated rule ID and revision | Integration |
| R08-02 | Multiple reasons | More than one matching rule | Return all reasons in the agreed order | Integration |
| R08-03 | No matching rule | Decision without a match | Defined contractual reason or message without fabricated data | Unit and integration |
| R08-04 | Preserve history after rule changes | Change parameters after a decision | Snapshot and revision of the previous decision remain unchanged | Integration |
| R08-05 | Missing decision | Valid but unknown UUID | Contractual 404 response | API |
| R08-06 | Read permission | No JWT, unauthorized role, authorized role | 401, 403, and successful response respectively | API |
| R08-07 | Missing or boundary data | Empty message, maximum length, over-limit message, and null rule_id | Follow validation and final contract | Unit |
| R08-08 | Sensitive data | Payment information in details | Output only data permitted by the agreed policy | Security / API |
| R08-09 | Pagination | Zero, one, and many reasons | Results and ordering follow the pagination contract | Integration, if supported |
