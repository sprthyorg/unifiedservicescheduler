# RAID Log (Risks, Assumptions, Issues, Dependencies)

Assumptions and dependencies are kept in `01-requirements/assumptions_v1.0.md` (A-xx, D-xx) and are not repeated here.
Last reviewed: 2026-10-15.

## Risks

| ID | Risk | Likelihood | Impact | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| R-01 | A race condition allows double-booking under concurrent requests. | Med | High | Per-dealership advisory lock plus DB exclusion constraints (ADR-002); concurrency tests in memory and on PostgreSQL. | Eng lead | Mitigated |
| R-02 | DMS or CRM reference data is late or of poor quality (wrong skills or shifts), so the schedule is wrong. | High | High | Validate ETL (skills/capabilities vocabulary, shift sanity); pilot with 3 dealerships; data-quality dashboard. | Data lead | Open |
| R-03 | Advisors keep using paper diaries, so there are two sources of truth. | Med | High | Cut-over plan C-01; training; diary retired per wave. | Product owner | Open |
| R-04 | Time zone or DST bugs (multi-zone network, future DST rules). | Low | Med | UTC storage; IANA zones; `tzdata` pinned and updated monthly (`maintenance_v1.0.md`). | Eng lead | Mitigated |
| R-05 | Fixed durations (A-08) misrepresent real job times, so bays overrun. | Med | Med | Track actual vs planned in 1.1; tune per service type; optional buffer (Q-02). | Workshop ops | Open |
| R-06 | Notification relay not in 1.0, so customers get no confirmation message. | High | Low | Confirmation shown in the app and portal; advisor tells walk-ins; relay in 1.1 (M3). | Eng lead | Accepted |
| R-07 | AI-generated code contains subtle defects. | Med | High | Mandatory human review (`releases/v1.0.0/approvals.md`); test evidence; pen test before go-live. | Eng lead | Open |

## Issues

| ID | Issue | Raised | Action | Status |
|---|---|---|---|---|
| I-01 | No named product owner yet for the Ownership domain; sign-off blocked. | 2026-10-15 | Escalate to domain head. | Open |
