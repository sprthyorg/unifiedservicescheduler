# ADR-001: One scheduler service owning its own PostgreSQL database

- **Status:** Accepted
- **Date:** 2026-10-15
- **Requirements:** FR-01..FR-10, NFR-04, NFR-05, NFR-15; assumptions A-03, A-17

## Context
Booking must check two resource types (technician, bay) and the vehicle, then write an appointment
atomically. The workload is modest (≤ 600 RPS, capacity estimate). Reference data is mastered
upstream (A-03).

## Decision
Build **one deployable service** (`scheduler-service`) with internal layers (api / services /
domain / repositories) and its own PostgreSQL database. It holds read-only replicas of reference
data. Upstream systems stay the masters.

## Alternatives considered
| Option | Pros | Cons | Why rejected |
|---|---|---|---|
| Separate Resource, Availability and Booking microservices | Independent scaling and teams | The two-resource check becomes a distributed transaction or saga, so a double-booking window appears; more operational cost | Correctness (NFR-05) and cost (NFR-15) |
| Query DMS live for technicians and bays on each booking | No replication | Couples availability and latency to DMS; DMS has no interval locking | NFR-01, NFR-02 |
| Off-the-shelf scheduling SaaS | Fast start | Data residency (C-02); weak fit for skill × capability matching | C-02, FR-02 |

## Consequences
- Simple ACID transactions give the booking guarantee.
- The reference-data ETL becomes a dependency (D-01, D-02) and a data-quality risk (R-02).
- If the service later needs splitting, the `domain.ports` seams are the boundaries.
