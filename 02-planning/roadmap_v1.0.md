# Delivery Roadmap

| Field | Value |
|---|---|
| Document ID | USS-PLN-001 |
| Version | 1.0.0 |
| Status | Draft for planning review |
| Date | 2026-10-15 |

## Milestones

| Milestone | Target date | Scope | Exit criterion | Owner |
|---|---|---|---|---|
| **M0 — Baseline** | 2026-10-16 | Requirements v1.0, architecture, design, reference implementation 1.0.0 | SIGNOFF.md fully approved | Product owner |
| **M1 — Staging ready** | 2026-10-30 | Infrastructure (Terraform), CI/CD to staging, reference-data ETL (D-01, D-02), gateway route (D-03) | Smoke and load tests green in staging (NFR-02, NFR-03) | Eng lead |
| **M2 — Pilot (3 dealerships)** | 2026-11-16 | 1.0.0 in production behind gateway; advisors book via dealer portal; manual diary kept in parallel | 2 weeks with 0 double-bookings and SLO met | Product owner + SRE |
| **M3 — Release 1.1** | 2026-12-14 | Outbox relay and notifications (FR-10 complete), reschedule (FR-11), resource blocks (FR-12), OpenTelemetry tracing | CR-approved scope shipped; contract minor bump 1.1.0 | Eng lead |
| **M4 — Network roll-out** | 2027-01 to 2027-03 | Waves of ~200 dealerships per fortnight; one-time import of future manual bookings (C-01); manual systems retired | G-5: no dealership on spreadsheets or diaries | Product owner |

## Release train

| Version | Contents | Contract change |
|---|---|---|
| 1.0.0 | FR-01..FR-09, FR-10 (outbox write) | API 1.0.0 (new) |
| 1.1.0 | FR-10 relay, FR-11, FR-12 | API 1.1.0 (additive) |
| 2.0.0 (candidate) | Customer-chosen technician (FR-13), multi-technician jobs | API 2.0.0 if breaking |
