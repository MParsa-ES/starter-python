# S4-RSK Test Matrix (US-01A: Base Risk Assessment)

| Test ID   | Layer       | Scenario                                                               | Expected Status           | DB State                        |
|:----------|:------------|:-----------------------------------------------------------------------|:--------------------------|:--------------------------------|
| **TC-01** | API / E2E   | Valid `INTERNAL` transfer (`destination_account_id`)                   | `201 Created` (`APPROVE`) | 1 Assessment, 1 Reason, 1 Event |
| **TC-02** | API / E2E   | Valid `EXTERNAL` transfer (`destination_iban`)                         | `201 Created` (`APPROVE`) | 1 Assessment, 1 Reason, 1 Event |
| **TC-03** | Security    | Unauthenticated POST request                                           | `403 Forbidden`           | 0 records created               |
| **TC-04** | Validation  | Invalid `amount` (`0`, `-1`, float, bool, string, `>int64`)            | `400 Bad Request`         | 0 records created               |
| **TC-05** | Validation  | Unsupported currency (`USD` instead of `IRR`)                          | `400 Bad Request`         | 0 records created               |
| **TC-06** | Validation  | `INTERNAL` transfer missing `destination_account_id`                   | `400 Bad Request`         | 0 records created               |
| **TC-07** | Validation  | `INTERNAL` transfer providing `destination_iban`                       | `400 Bad Request`         | 0 records created               |
| **TC-08** | Validation  | Self-transfer (`source_account_id == destination_account_id`)          | `400 Bad Request`         | 0 records created               |
| **TC-09** | Validation  | `EXTERNAL` transfer missing `destination_iban`                         | `400 Bad Request`         | 0 records created               |
| **TC-10** | Validation  | `EXTERNAL` transfer providing `destination_account_id`                 | `400 Bad Request`         | 0 records created               |
| **TC-11** | Validation  | Malformed `destination_iban` (wrong prefix, length, or Persian digits) | `400 Bad Request`         | 0 records created               |
| **TC-12** | Validation  | Naive `occurred_at` timestamp without timezone                         | `400 Bad Request`         | 0 records created               |
| **TC-13** | Transaction | Simulated `DecisionEvent` failure inside `@transaction.atomic`         | `500` / `RuntimeError`    | Full rollback (0 orphans)       |
| **TC-14** | Integration | Full lifecycle: `POST` create followed by `GET` detail lookup          | `200 OK`                  | Snapshot matches input          |
| **TC-15** | Integration | PostgreSQL `CheckConstraint` blocks invalid direct ORM write           | `IntegrityError`          | Rejected by PostgreSQL          |
| **TC-16** | API / Read  | `GET` unknown `decision_id` returns RFC 9457 Problem Details           | `404 Not Found`           | Unchanged                       |