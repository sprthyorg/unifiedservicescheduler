# Requirements Traceability Matrix

| Field | Value |
|---|---|
| Document ID | USS-RTM-001 |
| Version | 1.0.0 |
| Date | 2026-10-15 |
| Baseline | requirements v1.0 ↔ scheduler-service 1.0.0 ↔ API contract 1.0.0 ↔ schema V001 |
| Machine-readable source | `traceability-matrix_v1.0.csv` (this page is generated from it — edit the CSV) |

Forward trace: scenario → business requirement → FR/NFR → architecture (ADR) → design (API, data) → code → test → status.
Paths in *code* are relative to `services/scheduler-service/`; tests live under its `tests/`.

## 1. Scenario → business requirements → functional requirements

| Scenario core requirement | BR | Realised by |
|---|---|---|
| 1. Resource Constrained Booking | BR-01 | FR-01, FR-09 (and FR-04 to help pick a time) |
| 2. Real-Time Availability Check (ServiceBay + qualified Technician, entire duration) | BR-02 | FR-02, FR-06, NFR-05, NFR-06 |
| 3. Confirmed Appointment Record (customer, vehicle, technician, bay) | BR-03 | FR-03, FR-05, FR-07, FR-08 |
| Task: replace manual booking systems | BR-04 | FR-04, FR-07, FR-10, constraint C-01 (roadmap M4) |

## 2. Full matrix

| ID | Requirement | Priority | Architecture | API | Data | Code | Tests | Status (1.0.0) |
|---|---|---|---|---|---|---|---|---|
| BR-01 | Request appointment for vehicle/service type/dealership/time | Must | - | - | - | - | via FR-01 FR-09 | Covered |
| BR-02 | Check bay + qualified technician for entire duration | Must | - | - | - | - | via FR-02 FR-04 FR-06 | Covered |
| BR-03 | Persist appointment linking customer/vehicle/technician/bay | Must | - | - | - | - | via FR-03 FR-05 FR-07 FR-08 | Covered |
| BR-04 | Replace manual booking systems | Must | roadmap M4 | - | - | - | via FR-04 FR-07 FR-10; cut-over C-01 | Partial (cut-over at M4) |
| FR-01 | Book appointment | Must | ADR-001; architecture §5 | POST /v1/appointments | appointments | app/services/scheduling_service.py::book_appointment; app/api/routes.py::book_appointment | test_fr_01_books_requested_vehicle_service_dealership_and_time; test_fr_01_rejects_unknown_references; test_fr_01_fr_03_post_creates_appointment | Implemented + tested |
| FR-02 | Real-time technician + bay check for entire duration | Must | ADR-002; ADR-003; ADR-005 | POST /v1/appointments (409 SLOT_UNAVAILABLE) | ex_no_technician_double_booking; ex_no_bay_double_booking; ix_appointments_dealership_start | app/domain/allocation.py::choose/free_technicians/free_bays; UnitOfWork.lock_dealership | test_fr_02_* (14 tests incl. concurrent race in-memory + PostgreSQL) | Implemented + tested |
| FR-03 | Persistent confirmed appointment record | Must | ADR-001; ADR-004 | POST /v1/appointments 201 + Location; Appointment schema | appointments (FKs; reference UK) | app/domain/models.py::Appointment.confirm; repositories/*::add | test_fr_03_persists_record_linking_customer_vehicle_technician_and_bay; test_fr_03_failed_booking_leaves_no_record; test_fr_03_record_round_trips_through_postgres | Implemented + tested |
| FR-04 | Availability query | Should | ADR-005 | GET /v1/availability | ix_appointments_dealership_start | scheduling_service.py::availability; allocation.capacity/candidate_slots | test_fr_04_availability; test_fr_04_availability_lists_slots_and_shrinks_as_resources_are_booked; test_fr_04_availability_excludes_past_and_lead_time | Implemented + tested |
| FR-05 | Retrieve / list appointments | Must | - | GET /v1/appointments/{id}; GET /v1/appointments?customer_id= | ix_appointments_customer_start | scheduling_service.py::get_appointment/list_for_customer | test_fr_05_get_and_list; test_fr_05_get_and_list_customer_appointments | Implemented + tested |
| FR-06 | Alternatives on conflict | Should | ADR-003 | 409 SlotUnavailableProblem.alternatives | - | scheduling_service.py::_alternatives | test_fr_06_conflict_offers_nearest_alternative_slots; test_fr_02_fr_06_conflict_is_409_with_alternatives | Implemented + tested |
| FR-07 | Cancel appointment releasing resources | Should | ADR-002 (constraint WHERE status=CONFIRMED) | POST /v1/appointments/{id}/cancel | appointments.status/version/cancelled_at | models.py::Appointment.cancel; scheduling_service.py::cancel_appointment | test_fr_07_cancel; test_fr_07_cancel_rules; test_fr_07_cancel_releases_technician_and_bay; test_fr_07_cancel_frees_the_slot_in_postgres | Implemented + tested |
| FR-08 | Idempotent booking | Must | ADR-002 §3 | Idempotency-Key header; 200 Idempotent-Replayed; 409 IDEMPOTENCY_KEY_REUSED | uq_appointment_idempotency; request_hash | BookAppointmentCommand.fingerprint; book_appointment | test_fr_08_* (5 tests) | Implemented + tested |
| FR-09 | Booking validation rules (a)-(f) | Must | ADR-005 | 422 codes; 409 VEHICLE_ALREADY_BOOKED | ex_no_vehicle_double_booking | scheduling_service.py::_validate_start; book_appointment | test_fr_09_* (4 tests; 6 time cases) | Implemented + tested |
| FR-10 | Domain events via outbox | Could | ADR-004 | 04-design/events/*/v1.schema.json | outbox | app/domain/events.py; repositories/*::_Outbox | test_fr_10_events_match_published_schemas | Partial (outbox write; relay in 1.1) |
| FR-11 | Reschedule | Won't (1.0) | roadmap 1.1 | - | - | - | - | Deferred |
| FR-12 | Resource blocks (leave / maintenance) | Won't (1.0) | roadmap 1.1 | - | - | - | - | Deferred |
| FR-13 | Customer picks technician | Won't (1.0) | ADR-003 | - | - | - | - | Deferred |
| FR-14 | Reference data admin UI | Won't (1.0) | ADR-001 | - | - | - | - | Deferred |
| NFR-01 | 99.9% monthly | Must | ADR-006; HPA min 3 + topology spread; PDB | - | RDS Multi-AZ | deploy/k8s/base/* | SLO burn alerts (deploy/observability/alerts.yml) | Designed; verify in production |
| NFR-02 | Booking p95<=500ms; availability p95<=300ms; get p95<=200ms | Must | capacity-estimation §3 | - | indexes | app/observability.py histograms | local baseline p95 2.8 ms booking / 2.5 ms availability (test-evidence.md); k6 in staging pending | Baseline measured; load test pending (M1) |
| NFR-03 | 50 bookings/s + 550 reads/s for 30 min | Must | HPA 3-12 | - | - | - | k6 profile (test-strategy §5) | Pending (M1) |
| NFR-04 | Horizontal; 3000 dealerships no schema change | Must | ADR-001; architecture §8 | - | dealership_id on all hot queries | stateless app | architecture review | Designed |
| NFR-05 | Zero double-booking (DB-enforced) | Must | ADR-002 | - | 3 GiST exclusion constraints | lock_dealership; postgres.py ExclusionViolation mapping | test_fr_02_concurrent_requests_never_double_book (x2); test_nfr_05_exclusion_constraint_blocks_overlap_even_if_app_logic_is_bypassed | Implemented + tested |
| NFR-06 | 0 staleness in decision path | Must | ADR-002 | - | - | no cache; reads inside booking tx | design review; concurrency tests | Implemented |
| NFR-07 | RPO<=5min; RTO<=1h | Must | ADR-006 | - | RDS PITR 35d; cross-region snapshot | deploy/terraform/envs/production/main.tf | quarterly restore drill (maintenance M-06) | Designed; drill pending |
| NFR-08 | OAuth2 at gateway; TLS1.2+; ASVS L2; 0 HIGH/CRIT CVEs | Must | architecture §7 | bearerAuth; 404 for not-owner | least-privilege roles | non-root read-only image; NetworkPolicy; split secrets | Trivy + pip-audit in CI; test_fr_07_cancel_rules (not-owner 404); pen test pending | Partially verified |
| NFR-09 | Minimal PII; 3y retention; India residency | Must | architecture §7 | - | customers.display_name only | ID-only logging | data-model review; maintenance M-04 | Designed |
| NFR-10 | RED metrics + JSON logs + alerts->runbook | Must | monitoring_v1.0.md | /metrics; /health/* | - | app/observability.py; business counters | test_nfr_10_health_metrics_and_request_id | Implemented + tested |
| NFR-11 | Zero-downtime; rollback<=10min | Must | ADR-006 | - | forward-only migrations | .github/workflows/ci-cd.yml; Argo Rollouts | kustomize build validated; rollback drill pending (M-07) | Designed |
| NFR-12 | FR tests; mypy strict; ruff; layer contract | Must | architecture §4 | - | - | pyproject.toml (ruff mypy importlinter) | CI quality job (all green 2026-10-15) | Implemented + verified |
| NFR-13 | Versioned OpenAPI; RFC 9457 | Must | VERSIONING.md | openapi_1.0.0.yaml | - | app/api/errors.py | test_spec_and_implementation_expose_the_same_operations; test_spec_request_schema_matches_pydantic_required_fields | Implemented + tested |
| NFR-14 | UTC storage; IANA zone rules; DST-safe | Must | ADR-005 | UTC in Appointment; local offset in availability | timestamptz | models.py TimeRange/DailyWindow | test_time_range_is_half_open; test_fr_02_within_opening_hours_checks_whole_duration; test_fr_01_fr_03_post_creates_appointment | Implemented + tested |
| NFR-15 | <= USD 2500/month at design load | Should | ADR-001; ADR-006 | - | db.r6g.large | - | monthly cost report | Pending (post go-live) |

## 3. Coverage summary

| Measure | Value |
|---|---|
| Functional requirements in 1.0 scope (Must/Should/Could) | 10 of 14 |
| In-scope FRs with ≥ 1 automated test | 10 / 10 (100 %) |
| Deferred FRs (Won't 1.0) | FR-11, FR-12, FR-13, FR-14 |
| NFRs with automated verification in 1.0.0 | NFR-05, NFR-10, NFR-12, NFR-13, NFR-14 |
| NFRs needing environment evidence before go-live | NFR-01, NFR-02 (load), NFR-03, NFR-07 (restore drill), NFR-08 (pen test), NFR-11 (rollback drill), NFR-15 |

## 4. Backward trace (orphan check)

Every source module and test file traces to at least one requirement:

| Artefact | Requirements |
|---|---|
| `app/domain/allocation.py` | FR-02, FR-04, FR-06 |
| `app/domain/models.py` | FR-03, FR-07, NFR-14 |
| `app/domain/events.py`, outbox adapters | FR-10 |
| `app/services/scheduling_service.py` | FR-01..FR-09 |
| `app/api/*` | FR-01..FR-09, NFR-13 |
| `app/repositories/postgres.py` | FR-03, NFR-05 |
| `app/observability.py` | NFR-10 |
| `migrations/V001__init_schema.sql` | FR-03, FR-08, FR-09(f), NFR-05 |
| `deploy/**`, `.github/workflows/**` | NFR-01, NFR-04, NFR-07, NFR-08, NFR-11 |
| `tests/test_allocation.py` | FR-02, NFR-14 (plus allocation policy ADR-003) |
| `tests/contract/*` | NFR-13, FR-10 |

## Revision history

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.0 | 2026-10-15 | Claude Code | Initial matrix for release 1.0.0. |
