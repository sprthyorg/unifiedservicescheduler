# Release 1.0.0 — Unified Service Scheduler

**Date:** 2026-10-15 · **Status:** release candidate (see `approvals.md`)

## Highlights
- **Book a service appointment** for a vehicle, service type, dealership and time (FR-01).
- **Real-time two-resource check:** a booking is confirmed only when a qualified technician *and* a compatible bay are free for the entire duration. The system allocates both (FR-02, ADR-002, ADR-003).
- **Persistent appointment record** linking customer, vehicle, technician and bay, with a human-readable reference (FR-03).
- Availability search (FR-04), retrieval (FR-05), nearest alternatives on conflict (FR-06), cancellation (FR-07), idempotent retries (FR-08), validation rules (FR-09), outbox events (FR-10, relay in 1.1).
- **Zero double-booking guaranteed by the database:** GiST exclusion constraints on technician, bay and vehicle (NFR-05).

## API
`/v1` contract 1.0.0 (`04-design/api/scheduler-service/v1/openapi_1.0.0.yaml`). New, so there are no breaking changes.

## Database
Migration `V001__init_schema.sql` (requires the `btree_gist` extension). `V002` demo seed is applied in non-production environments only.

## Known limitations
| Item | Workaround | Planned |
|---|---|---|
| No outbox relay, so no SMS or email confirmations | Confirmation shown in the app and portal | 1.1.0 |
| No reschedule endpoint | Cancel, then rebook | 1.1.0 |
| No technician leave or bay maintenance blocks | Mark the resource inactive in DMS | 1.1.0 |
| Region-loss RPO 24 h | Accepted for 1.0 | Revisit at M4 |

## Upgrade / deploy notes
1. Run the one-time DB bootstrap from `deploy/README.md`.
2. Load reference data through the ETL (D-01, D-02).
3. Deploy through the pipeline. The migration Job runs before the API rollout.
