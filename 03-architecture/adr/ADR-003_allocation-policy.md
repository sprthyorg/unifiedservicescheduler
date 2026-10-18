# ADR-003: The system allocates the resources: least-loaded technician, best-fit bay

- **Status:** Accepted
- **Date:** 2026-10-15
- **Requirements:** FR-02, FR-03, FR-13; assumption A-11

## Context
Several technicians and bays may qualify for a slot. Which ones we assign affects fairness,
utilisation and future availability (specialised bays are scarce).

## Decision
The client never names a technician or bay (`additionalProperties: false` rejects them). Among the free candidates:
- **Technician:** the fewest minutes already booked that local day, tie-broken by ID. This spreads work.
- **Bay:** the fewest capabilities that still satisfy the requirement (best fit), tie-broken by ID. This keeps
  alignment or EV bays free for jobs that need them.

The algorithm is a pure function (`app/domain/allocation.py::choose`) and is deterministic for testability.
Remaining capacity for a slot is `min(free qualified technicians, free compatible bays)`. This is exact
because any qualified technician can work in any compatible bay (complete bipartite graph).

## Alternatives considered
| Option | Pros | Cons | Why rejected |
|---|---|---|---|
| Customer picks the technician | Personal preference | Fragmented availability; lower utilisation | A-11; possible 2.0 feature (FR-13) |
| First free by ID | Simplest | Overloads low-ID technicians; wastes special bays | Fairness, utilisation |
| Global optimiser (ILP or CP-SAT) over the whole day | Best packing | Re-shuffles existing bookings; heavy; non-local | Overkill for 1.0 |

## Consequences
Policy changes (for example, a preferred-technician weighting) are local to `choose()` and its unit tests.
