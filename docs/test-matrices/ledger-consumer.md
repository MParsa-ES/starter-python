# Consumer test matrix: S2-LDG ledger client

The client in `s4_rsk/integrations/ledger_client.py` is tested. The original matrix preceded its integration with `assessments.services` (US-01B). Stub responses are based on `openapi/neighbors/s2_ldg.yaml`; rerun the tests if the actual S2 contract replaces it.

| ID | Scenario | Stub response / input | Expected result | Edge case | Automated test |
|---|---|---|---|---|---|
| L-01 | Successful response | 200 with two debits | Two parsed entries, OK status, no forced decision; request includes `direction=DEBIT`, `from`, and `X-Correlation-ID` | No | `test_success_returns_parsed_debits_and_sends_the_draft_request` |
| L-02 | Pagination | First page has `next_cursor` | Request the next page with that cursor and combine results | Yes | `test_pagination_follows_next_cursor_until_exhausted` |
| L-03 | Unknown account | 404 Problem Details | `ACCOUNT_NOT_FOUND` and forced REVIEW | Yes | `test_unknown_account_forces_review_with_explicit_reason` |
| L-04 | Timeout | `ConnectTimeout` exception | `LEDGER_UNAVAILABLE` and REVIEW without propagating the error | Yes | `test_timeout_forces_review_instead_of_raising` |
| L-05 | Server error | 503 Problem Details | `LEDGER_UNAVAILABLE` and REVIEW | Yes | `test_server_error_forces_review` |
| L-06 | Incomplete body | 200 without `amount` | Reject the data and return REVIEW | Yes | `test_malformed_success_body_is_not_trusted` |
| L-07 | Neighbor address | `NEIGHBOR_BASE_URL` | Send the request to the configured host and port | No | `test_neighbor_base_url_environment_variable_selects_the_host` |
| L-08 | Missing address | No environment variable | Clear error rather than a guessed address | Yes | `test_missing_neighbor_base_url_is_a_clear_error` |
| L-09 | Unexpected 4xx | 403 | Error rather than empty history; forced REVIEW | Yes | `test_unexpected_client_error_is_not_treated_as_empty_history` |
| L-10 | Endless cursor chain | Every page has `next_cursor` | Stop with an error after the page limit | Yes | `test_endless_cursor_chain_is_cut_off` |
| L-11 | Service token | Client configured with `token` | Send the `Authorization: Bearer` header | No | `test_bearer_token_is_sent_when_configured` |
| L-12 | Contract test against Prism or a real neighbor | `NEIGHBOR_BASE_URL` | Success and error responses match the neighbor contract | No | `test_ledger_contract.py` (`contract` marker) |

## Coverage gaps

- Service-to-service authentication with S2 still requires agreement with the S2 team; only sending the header is tested (L-11), not acceptance by S2.
- Retry with backoff is intentionally not implemented; failures produce a REVIEW signal, according to the session 4 sequence diagram.
