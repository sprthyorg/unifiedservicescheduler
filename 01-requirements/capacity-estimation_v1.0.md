# Capacity Estimation (back of the envelope)

| Field | Value |
|---|---|
| Document ID | USS-CAP-001 |
| Version | 1.0.0 |
| Status | Baselined |
| Date | 2026-10-15 |
| Basis | Assumption A-02. Re-run this sheet whenever A-02 changes; NFR-03, NFR-04 and NFR-15 follow from it. |

## 1. Bookings

| Quantity | Calculation | Result |
|---|---|---|
| Dealerships (year 1) | A-02 | 1,200 |
| Bays per dealership | A-02 | 8 → 9,600 bays |
| Jobs per bay per day | A-02 (≈ 10 h open ÷ ~2 h average job) | 5 |
| Appointments per day | 9,600 × 5 | **≈ 48,000** |
| Booking writes per day (+15 % cancellations and rebookings) | 48,000 × 1.15 | ≈ 55,000 |
| Average booking rate (over 10 business hours) | 55,000 / 36,000 s | ≈ 1.5 /s |
| Peak factor (Monday morning, campaign days) | × 3 | ≈ 4.6 /s |
| **Design target (≈ 10× peak: growth to 3,000 dealerships and campaign spikes)** | | **50 bookings/s** (NFR-03) |

## 2. Request mix at design target

| Request | Per booking | RPS at 50 bookings/s |
|---|---|---|
| `GET /v1/availability` | ~8 (customer browses dates) | 400 |
| `POST /v1/appointments` | 1 (+ ~10 % rejected and retried) | 55 |
| `GET /v1/appointments*` | ~2 | 100 |
| Reference lists | ~1 (cacheable at the edge) | 45 |
| **Total** | | **≈ 600 RPS**. Read:write ≈ 10:1 |

## 3. Cost of one availability or booking decision

- One dealership day holds at most ~40 confirmed appointments (8 bays × 5).
- A day has at most 40 candidate start times (10 h ÷ 15 min).
- Each candidate is checked against ≤ 10 technicians and ≤ 8 bays, each against ≤ 40 bookings: ~30k comparisons, under 5 ms of CPU in Python.
- The database reads one indexed range (`ix_appointments_dealership_start`) plus small reference sets, which is cheap.
- **Measured locally** (Docker Compose, single client, 2026-10-15): availability p95 = **2.5 ms**, booking p95 = **2.8 ms** (`releases/v1.0.0/test-evidence.md`). That leaves ample headroom against NFR-02. The staging load test is still required.

## 4. Lock contention (ADR-002)

| Quantity | Calculation | Result |
|---|---|---|
| Bookings per dealership, average at design target | 50 / 1,200 | 0.04 /s |
| Busiest dealership (× 5 average) | | 0.2 /s |
| Lock hold time per booking (read, decide, insert) | measured < 10 ms | 10 ms |
| Lock utilisation at the busiest dealership | 0.2 × 0.01 | **0.2 %**: queueing is negligible |

Serialising decisions per dealership costs nothing measurable at this scale. Global serialisation
would be 50 × 0.01 = 50 % utilisation, which is why the lock is per dealership and not global.

## 5. Storage

| Data | Row size (incl. index share) | Rows per year | Year 1 | 3-year retention (A-19) |
|---|---|---|---|---|
| appointments | ~1.2 KB | 48k × 365 × 1.15 ≈ 20 M | ~24 GB | ~72 GB |
| outbox (purged after 7 days) | ~1 KB | ~770k live | < 1 GB | < 1 GB |
| reference data | — | ~25k technicians, ~10k bays, ~5 M vehicles | ~2 GB | ~3 GB |
| **Total** | | | **~27 GB** | **~76 GB** |

A **single PostgreSQL primary** (db.r6g.large, Multi-AZ, 200 GB gp3) is enough for 3 years.
Partitioning `appointments` by `start_at` month is noted as a 2.0 option, not needed now.

## 6. Compute

- About 150 RPS per API pod (2 uvicorn workers at 250m to 1 vCPU) → 600 RPS needs 4 pods. Run at least 3, with HPA up to 12, for AZ spread and headroom (NFR-04).
- DB connections: 12 pods × pool 10 = 120, within the RDS `max_connections` for r6g.large (~800).

## 7. Implications for the architecture

1. Read-heavy but small → no cache in the decision path (NFR-06). Availability is computed from indexed data on each request.
2. Correctness is the risk, not scale → database-enforced exclusion constraints plus a per-dealership lock (ADR-002).
3. One relational store is enough → a single service with its own PostgreSQL (ADR-001).
4. Stateless API → horizontal pod autoscaling (NFR-04).

## Revision history

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.0 | 2026-10-15 | Claude Code | Initial estimate from A-02; local latency baseline added. |
