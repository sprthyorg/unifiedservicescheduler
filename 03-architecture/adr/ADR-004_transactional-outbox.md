# ADR-004: Transactional outbox for appointment events

- **Status:** Accepted (relay delivered in 1.1)
- **Date:** 2026-10-15
- **Requirements:** FR-10, FR-03; assumption A-13

## Context
Notifications and analytics need to know about confirmations and cancellations. Publishing directly
to a broker after commit can lose events on a crash. Publishing before commit can announce bookings
that were rolled back.

## Decision
Write an `outbox` row in the **same transaction** as the appointment change. A separate relay (1.1)
polls `WHERE published_at IS NULL`, publishes to the bus with the event `id` as the idempotency key,
and sets `published_at`. Consumers must be idempotent (at-least-once delivery). Event schemas are
versioned in `04-design/events/`.

## Alternatives considered
| Option | Pros | Cons | Why rejected |
|---|---|---|---|
| Publish after commit | Simple | Lost events on a crash | Reliability |
| CDC (Debezium) on `appointments` | No outbox table | Leaks the table schema as the contract; extra infrastructure | Coupling |
| Synchronous call to the notification API | Immediate | Couples booking latency and availability to notifications | NFR-01, NFR-02 |

## Consequences
Outbox rows accumulate until the relay ships. They are purged 7 days after publication (`maintenance_v1.0.md`).
