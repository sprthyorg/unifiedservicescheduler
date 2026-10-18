# Service Level Objectives

| Field | Value |
|---|---|
| Document ID | USS-OPS-001 |
| Version | 1.0.0 |
| Date | 2026-10-15 |
| Derived from | NFR-01, NFR-02, NFR-05, NFR-07 |

SLOs are measured over a rolling 30 days at the ingress. When the error budget is spent, feature
releases pause and the team works on reliability until the budget recovers.

| Journey | SLI (good / valid events) | SLO | Error budget (30 d) |
|---|---|---|---|
| Book appointment | `POST /v1/appointments` responses that are non-5xx **and** < 500 ms | **99.9 %** | 0.1 % of requests (≈ 43 min equivalent) |
| Check availability | `GET /v1/availability` non-5xx and < 300 ms | **99.5 %** | 0.5 % |
| View appointment(s) | `GET /v1/appointments*` non-5xx and < 200 ms | **99.9 %** | 0.1 % |
| Booking integrity | Overlapping CONFIRMED pairs (technician, bay or vehicle) | **0** (absolute) | none: any breach is a Sev-1 |
| Data durability | Committed appointments recoverable after restore | 100 % (RPO 5 min) | — |

**4xx responses count as good events.** `409 SLOT_UNAVAILABLE`, `422` validation failures and
replays mean the system behaved correctly.

## Burn-rate alerting (multi-window)

| Severity | Long window | Short window | Burn rate | Budget consumed when it fires | Rule |
|---|---|---|---|---|---|
| Page | 1 h | 5 min | 14.4× | 2 % | `SchedulerApiErrorBudgetBurnFast` |
| Page | 6 h | (for 30 min) | 6× | 5 % | `SchedulerApiErrorBudgetBurnSlow` |
| Ticket | 3 d | — | 1× | 10 % | weekly SLO review |

Rules are in `deploy/observability/alerts.yml`.
