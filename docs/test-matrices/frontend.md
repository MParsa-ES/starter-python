# Frontend test matrix (Vitest and React Testing Library component tests)

| ID | Scenario | Input (mock fetch) | Expected result | Edge case | Test |
|---|---|---|---|---|---|
| F-01 | Successful health check | 200 with `{status: UP}` | Backend availability message and service JSON | No | `App.extra.test.tsx` |
| F-02 | Network failure | `fetch` rejects | An error including `Failed to fetch` | Yes | `App.extra.test.tsx` |
| F-03 | Unknown route | `/abc` | 404 page | Yes | `App.extra.test.tsx` |
| F-04 | Problem Details | 503 with `application/problem+json` | Display title, code, detail, and `correlation_id` | Yes | `App.extra.test.tsx` |
| F-05 | HTTP error without Problem Details | 500 with plain text | Generic `HTTP 500` message without fabricated details | Yes | `App.extra.test.tsx` |
| F-06 | Retry | Click the retry button | `fetch` is called again | No | `App.extra.test.tsx` |

## Coverage notes

- Rule management component tests are in `RulesPage.test.tsx`.
- Playwright end-to-end coverage was not required in session 5; only the tool was installed.
