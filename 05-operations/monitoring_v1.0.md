# Monitoring

| Field | Value |
|---|---|
| Document ID | USS-OPS-002 |
| Version | 1.0.0 |
| Date | 2026-10-15 |
| Requirement | NFR-10 |

## 1. Signals emitted by scheduler-service

| Signal | Name / field | Labels | Source |
|---|---|---|---|
| Request rate and errors | `http_requests_total` | `service, method, route (templated), status` | `app/observability.py` middleware |
| Latency | `http_request_duration_seconds` (histogram; buckets 25 ms to 5 s) | `service, method, route` | middleware |
| Bookings confirmed | `scheduler_appointments_confirmed_total` | `dealership_id` | `app/api/routes.py` |
| Booking rejections | `scheduler_booking_rejections_total` | `code` (`SLOT_UNAVAILABLE`, `OUTSIDE_BUSINESS_HOURS`, …) | `app/api/errors.py` |
| Access log | JSON: `ts, level, request_id, method, path, status, duration_ms` | — | stdout |
| Domain log | JSON: `appointment_id, dealership_id, code` | — | `scheduling` and `errors` loggers |
| Integrity backstop | log with `code = EXCLUSION_BACKSTOP` | — | `app/repositories/postgres.py` |
| Health | `/health/live` (process), `/health/ready` (database ping) | — | Kubernetes probes |

The `X-Request-ID` header is accepted or generated, and echoed back, so client and server logs can
be correlated. Logs never contain names, phone numbers or VINs; only IDs are logged (NFR-09).

## 2. Dashboards (Grafana)

| Dashboard | Panels |
|---|---|
| **Scheduler: golden signals** | RPS by route; 5xx ratio; p50/p95/p99 by route against the NFR-02 thresholds; pods ready; HPA replicas |
| **Scheduler: business** | Confirmed bookings per minute (total and top-10 dealerships); rejection mix by `code`; ratio of SLOT_UNAVAILABLE to attempts by dealership |
| **Scheduler: database** | RDS CPU, connections against the pool, slow queries (> 250 ms), replication lag, free storage, `pg_locks` waiting on advisory locks |
| **SLO** | 30-day budget remaining per journey; burn rate |

## 3. Alerts → runbook

| Alert | Severity | Runbook |
|---|---|---|
| SchedulerApiErrorBudgetBurnFast / Slow | page | RB-01 |
| BookingLatencyHigh | page | RB-02 |
| AvailabilityLatencyHigh | ticket | RB-02 |
| SlotUnavailableRatioHigh | ticket | RB-03 |
| EXCLUSION_BACKSTOP log alert | page | RB-04 |
| SchedulerNotReady | page | RB-05 |
| RDS: CPU > 80 % for 15 min, free storage < 20 %, replica lag > 60 s (CloudWatch) | ticket | RB-06 |

## 4. Planned for 1.1
OpenTelemetry tracing (gateway → API → DB) and an outbox backlog gauge (`scheduler_outbox_unpublished`) with an alert once the relay ships.
