# Risk dashboard test matrix (US-03)

| Test ID | Scenario | Path | Category | Coverage | Corresponding test / reason for missing coverage |
|---|---|---|---|---|---|
| `TC-001` | Retrieve statistics for a valid range (`start` < `end`) and calculate decisions correctly | Happy path | Backend (unit) | Covered | `test_valid_range_returns_statistics`, `test_valid_range_is_accepted` |
| `TC-002` | Fill decision types missing from database results with zero | Happy path | Backend (unit) | Covered | `test_missing_decision_types_are_filled_with_zero` |
| `TC-003` | Request a reversed range (`start` > `end`); return 400 | Edge case | Backend (unit) | Covered | `test_reversed_range_returns_400_problem_details`, `test_reversed_range_is_rejected` |
| `TC-004` | Request statistics with missing required parameters or malformed values; return 400 | Edge case | Backend (unit) | Covered | `test_missing_parameters_return_400`, `test_missing_or_malformed_values_are_rejected` |
| `TC-005` | Request an empty range (`start` == `end`); return zeros | Edge case | Backend (unit) | Covered | `test_empty_range_gives_all_zeros`, `test_start_equal_to_end_is_an_empty_but_valid_range` |
| `TC-006` | Include `X-Correlation-ID` in a successful response | Happy path | Backend (unit) | Covered | `test_response_carries_the_correlation_header` |
| `TC-007` | Count decisions and filter by time range in PostgreSQL | Happy path | Backend (integration) | Covered | `test_count_decisions_by_type_groups_correctly`, `test_count_decisions_by_type_respects_time_range` |
| `TC-008` | Count open manual review queue items (`queue_size_now`) from the database | Happy path | Backend (integration) | Not covered | Depends on `ManualReviewItem` (US-04A), which was not implemented when this matrix was written. |
| `TC-009` | Display the dashboard and automatically call the API when the date filter changes | Happy path | Frontend | Not covered | Dashboard frontend (US-03B) was not planned for this sprint. |
| `TC-010` | Clearly display backend validation errors (Problem Details) in the UI | Edge case | Frontend | Not covered | The dashboard frontend component had not yet been developed. |
