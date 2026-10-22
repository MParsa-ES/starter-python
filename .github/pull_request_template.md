## Jira Issue & User Story
- Jira Ticket: RSK-___
- User Story: US-0_

## Summary of Changes
- 

## LabBank Technical Standards Checklist
- [ ] GEN-01 / GEN-02: Endpoint is under /api/v1/ and documented with OpenAPI (drf-spectacular).
- [ ] GEN-03: Money fields use 64-bit integer (BigIntegerField) in IRR (no float/double).
- [ ] GEN-04: Public identifiers use UUIDv7 (uuid6.uuid7).
- [ ] GEN-05: Timestamps are stored/returned in UTC; daily boundaries use Asia/Tehran.
- [ ] GEN-06: Errors return RFC 9457 application/problem+json format.
- [ ] GEN-07 / GEN-08: Mutating POST endpoints support Idempotency-Key and propagate X-Correlation-ID.
- [ ] Tests: Unit and integration tests (pytest) added and passing.