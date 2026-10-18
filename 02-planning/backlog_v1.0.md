# Product Backlog — Release 1.0

| Field | Value |
|---|---|
| Document ID | USS-PLN-002 |
| Version | 1.0.0 |
| Date | 2026-10-15 |

Estimates are story points (Fibonacci). "Done" means the definition of done in `00-ai-instructions/CLAUDE.md` §6 is met.

| Story | As a… I want… so that… | Reqs | Pts | Status |
|---|---|---|---|---|
| US-01 | As a customer, I want to book a service for my vehicle at a dealership and time, so that I don't have to phone. | FR-01, FR-09 | 5 | Done (1.0.0) |
| US-02 | As a workshop manager, I want a booking confirmed only when a qualified technician and a suitable bay are free for the whole job, so that the shop floor is never double-booked. | FR-02, NFR-05, NFR-06 | 8 | Done (1.0.0) |
| US-03 | As a service advisor, I want every booking stored with its technician and bay, so that the day plan is accurate. | FR-03 | 3 | Done (1.0.0) |
| US-04 | As a customer, I want to see which times are free, so that I pick one that will succeed. | FR-04 | 5 | Done (1.0.0) |
| US-05 | As a customer, I want to view my appointments. | FR-05 | 2 | Done (1.0.0) |
| US-06 | As a customer, when my time is taken I want nearby alternatives, so that I can rebook in one step. | FR-06 | 3 | Done (1.0.0) |
| US-07 | As a customer, I want to cancel, so that the slot is freed for others. | FR-07 | 3 | Done (1.0.0) |
| US-08 | As a mobile client, I want retries to be safe, so that a flaky network never creates duplicate bookings. | FR-08 | 3 | Done (1.0.0) |
| US-09 | As the notification platform, I want booking events, so that customers get confirmations. | FR-10 | 5 | Partially done: outbox in 1.0.0, relay in 1.1 |
| US-10 | As an SRE, I want metrics, alerts and runbooks, so that I can run the service to its SLO. | NFR-01, NFR-10 | 5 | Done (1.0.0 artefacts) |
| US-11 | As an SRE, I want a pipeline with canary and rollback. | NFR-11 | 5 | Done (pipeline defined; first run at M1) |
| US-12 | As the data team, I want reference data loaded from DMS and CRM. | A-03, D-01, D-02 | 8 | To do (M1) |
| US-13 | As a customer, I want to reschedule in one step. | FR-11 | 5 | To do (1.1) |
| US-14 | As a workshop manager, I want to block a technician's leave or a bay's maintenance. | FR-12 | 8 | To do (1.1) |
| US-15 | As the business, I want existing future bookings imported at cut-over. | C-01 | 5 | To do (M4) |
