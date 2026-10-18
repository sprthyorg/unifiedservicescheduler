# Changelog — scheduler-service

All notable changes to this service. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [SemVer](https://semver.org/) — see `../../VERSIONING.md`.

## [1.0.0] — 2026-10-15
### Added
- `POST /v1/appointments` — resource-constrained booking with technician + bay allocation (FR-01, FR-02, FR-03).
- `GET /v1/availability` — bookable start times with remaining capacity (FR-04).
- `GET /v1/appointments/{id}`, `GET /v1/appointments?customer_id=` (FR-05).
- Nearest alternative slots in `409 SLOT_UNAVAILABLE` responses (FR-06).
- `POST /v1/appointments/{id}/cancel` releasing resources (FR-07).
- Mandatory `Idempotency-Key` on booking (FR-08); booking validation rules (FR-09).
- `appointment.confirmed` / `appointment.cancelled` events written to the transactional outbox (FR-10, relay in 1.1.0).
- Schema `V001__init_schema.sql` with GiST exclusion constraints (NFR-05); demo seed `V002`.
- Health, readiness and Prometheus metrics endpoints (NFR-09).
