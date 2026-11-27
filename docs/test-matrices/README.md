# Test matrices

A test matrix records agreed expected behavior before tests are written or during review. A scenario describes a general situation; each case provides a concrete input, precondition, and expected result. For example, a limit validation scenario includes cases for 0, 1, and values above the maximum. Check boundary values, neighboring values, and empty or invalid inputs separately.

A matrix does not replace test execution. Compare each row with the API response and, where necessary, database state; reference actual test names in the automated test column. Team members can add a `us-XX.md` file with the story, assumptions, and the following table. Agree on uncertain outcomes with the team instead of presenting guesses as decisions.

| ID | Scenario and precondition | Input | Expected result | Level / automated test |
|---|---|---|---|---|
| XX-01 | ... | ... | ... | Unit / integration / manual; test name |

Unit tests cover individual components, integration tests cover collaboration such as API and PostgreSQL, and manual or end-to-end tests cover user workflows. Use test data and environments. Update the matrix and tests when the contract changes.

- [US-02 risk rule management](us-02.md)
- [US-08 decision explainability draft](us-08-draft.md)
- [Frontend tests](frontend.md)
- [Ledger consumer test draft](ledger-consumer.md)
