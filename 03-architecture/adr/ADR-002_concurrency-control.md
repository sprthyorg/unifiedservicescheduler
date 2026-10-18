# ADR-002: Per-dealership advisory lock plus database exclusion constraints

- **Status:** Accepted
- **Date:** 2026-10-15
- **Requirements:** FR-02, FR-08, NFR-05, NFR-06

## Context
Two customers can request overlapping times that compete for the last qualified technician or the
last compatible bay. The decision is "pick any free technician and any free bay", so there is no
single row to lock. Plain READ COMMITTED read-check-insert would allow both requests to succeed.

## Decision
1. Inside the booking transaction, take `pg_advisory_xact_lock(hashtextextended('dealership:<id>', 0))`
   **before** reading schedules. Decisions for one dealership are serialised; different dealerships
   never block each other. The lock is released automatically at commit or rollback.
2. Add **GiST exclusion constraints** on `appointments` for `(technician_id, period)`,
   `(service_bay_id, period)` and `(vehicle_id, period)` `WHERE status = 'CONFIRMED'`. Even a bug,
   a manual SQL insert or a future code path cannot create an overlap. Violations map to
   `409 SLOT_UNAVAILABLE` / `VEHICLE_ALREADY_BOOKED`.
3. The idempotency lookup happens **after** taking the lock, so concurrent retries with the same key
   see each other. `UNIQUE (customer_id, idempotency_key)` backs this up.

## Alternatives considered
| Option | Pros | Cons | Why rejected |
|---|---|---|---|
| SERIALIZABLE isolation with retry | No explicit lock | Retry storms under contention; harder to reason about; still needs retry plumbing | Complexity, tail latency |
| Optimistic: insert and rely only on the exclusion constraint, retrying with the next candidate | No lock | Many retries when a dealership is busy; the choice of technician is no longer deterministic | Less predictable; kept as the backstop instead |
| Pre-materialised slot rows with `SELECT … FOR UPDATE` | Familiar | Slot-table explosion (resources × 15-min slots × 90 days); variable durations span many rows | See ADR-005 |
| Redis or ZooKeeper distributed lock | Works across DBs | Another moving part; the lock is not tied to the DB transaction | Unnecessary; one DB |

## Consequences
- Lock utilisation is about 0.2 % at the busiest dealership at design load (capacity estimate §4).
- Requires the `btree_gist` extension (available on RDS).
- Verified by `tests/integration/test_postgres.py` (10-connection race; constraint test with the app bypassed).
