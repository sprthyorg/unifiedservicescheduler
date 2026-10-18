# Event catalogue and compatibility policy

| Event | Version | Emitted when | Schema | Producer code |
|---|---|---|---|---|
| `appointment.confirmed` | v1 | Booking committed (FR-03) | `appointment.confirmed/v1.schema.json` | `app/domain/events.py::appointment_confirmed` |
| `appointment.cancelled` | v1 | Cancellation committed (FR-07) | `appointment.cancelled/v1.schema.json` | `app/domain/events.py::appointment_cancelled` |

**Envelope:** `id` (dedup key), `type`, `schema_version`, `occurred_at`, `aggregate_id`, `payload`.
In 1.0 these are the columns of the `outbox` table; the 1.1 relay serialises them as the message.
Topic: `scheduler.appointments.v1`, keyed by `aggregate_id`, so all events for one appointment stay in order.

## Rules
1. **Additive change** (a new optional payload field) keeps the same `vN`; consumers must ignore unknown fields (`additionalProperties: true`).
2. **Breaking change** (removing or renaming a field, changing a type or meaning) needs a new `v(N+1).schema.json`. The producer dual-publishes `vN` and `vN+1` for at least 90 days, and the `vN` sunset date is announced in `CHANGELOG.md`.
3. Schemas are never edited after release. A fix is a new version.
4. Consumers are idempotent on `id`. Delivery is at-least-once (ADR-004).
