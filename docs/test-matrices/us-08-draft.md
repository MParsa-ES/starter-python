# Draft US-08 test matrix: decision explainability

This draft is not the final story specification. The current `DecisionReason` model includes code, message, rule_id, rule_revision, and rule_snapshot; the model alone does not prove the API or story is complete. The endpoint, permitted roles, response contract, number of reasons, and handling of sensitive data require team agreement.

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
