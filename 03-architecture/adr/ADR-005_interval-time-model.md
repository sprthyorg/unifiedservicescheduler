# ADR-005: Continuous intervals with aligned start times (no slot table)

- **Status:** Accepted
- **Date:** 2026-10-15
- **Requirements:** FR-02, FR-04, NFR-14; assumptions A-05, A-08, A-10

## Context
Service durations vary from 45 to 180 minutes. Availability must hold for the *entire* duration.

## Decision
Store each appointment as `[start_at, end_at)` (`timestamptz`) and compute conflicts with interval
overlap (`tstzrange &&` in SQL, `TimeRange.overlaps` in Python). Start times are restricted to a
15-minute grid in dealership local time (A-05). Opening hours and shifts are weekly local-time
templates evaluated in the dealership's IANA zone.

## Alternatives considered
| Option | Pros | Cons | Why rejected |
|---|---|---|---|
| Pre-generated 15-min slot rows per resource | Easy row locking | ~10k bays × 40 slots × 90 days ≈ 36 M rows plus technicians; a booking touches up to 12 rows; regeneration when shifts change | Size, complexity |
| Free-form start times | Flexible | Fragmented schedules; unbounded availability search | Utilisation; NFR-02 |

## Consequences
DST transitions are handled by `zoneinfo`. Overnight windows are out of scope (A-09).
