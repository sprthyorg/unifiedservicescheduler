# Requirements Specification — Unified Service Scheduler

| Field | Value |
|---|---|
| Document ID | USS-REQ-001 |
| Version | 1.0.0 |
| Status | Baselined, awaiting sign-off (`releases/v1.0/SIGNOFF.md`) |
| Date | 2026-10-15 |
| Inputs | `business-scenario_v1.0.md`, `assumptions_v1.0.md`, `capacity-estimation_v1.0.md` |
| Author | Claude Code (AI-generated; human review pending) |

Each requirement has a stable ID. IDs are never reused or renumbered; a removed requirement is
marked *Withdrawn*. Changes after the baseline go through a change request (`change-requests/`).
Priority uses MoSCoW for release 1.0.

## 1. Actors

| Actor | Description | Channel |
|---|---|---|
| Customer | Vehicle owner booking for their own vehicle. | Web or mobile app through the API gateway |
| Service advisor | Dealership staff booking on a customer's behalf (A-01, A-15). | Dealer portal through the API gateway |
| Upstream systems | Dealer-management system (bays, technicians, shifts, skills, hours) and CRM (customers, vehicles). | Reference-data replication (A-03) |
| Downstream consumers | Notification platform, analytics. | `appointment.*` events (FR-10) |

## 2. Domain glossary

| Term | Meaning |
|---|---|
| Service type | A catalogue job, such as an oil change. It has a fixed **duration**, a **required skill** and a **required bay capability**. |
| Service bay | A physical workspace at one dealership. It has a set of **capabilities**, such as `LIFT`, `ALIGNMENT_RIG` or `EV_SAFE`. |
| Technician | Works at one dealership. Has a set of **skills** and a weekly **shift** pattern. |
| Qualified technician | An active technician who holds the service type's required skill and whose shift covers the whole slot. |
| Compatible bay | An active bay at the dealership with the service type's required capability. |
| Slot | The half-open interval `[start, start + duration)`. |
| Appointment | The confirmed allocation of one technician and one bay to one vehicle for one slot. |

## 3. Functional requirements

| ID | Requirement | Priority | Traces to |
|---|---|---|---|
| FR-01 | **Book appointment.** A customer or advisor can request an appointment by giving the customer, vehicle, service type, dealership and desired start time. The system derives the end time from the service type's duration. | Must | BR-01 |
| FR-02 | **Real-time resource check.** Before confirming, the system checks against committed data at that moment that at least one *qualified technician* and one *compatible bay* are free for the **entire** slot. It allocates one of each, or rejects the request. | Must | BR-02 |
| FR-03 | **Confirmed appointment record.** On success the system persists an appointment that links the customer, vehicle, dealership, service type, technician, service bay, start, end, status `CONFIRMED` and a human-readable reference. A failed request leaves no record. | Must | BR-03 |
| FR-04 | **Availability query.** For a dealership, service type and local date, the system lists bookable start times and the remaining capacity at each. | Should | BR-01, BR-04 |
| FR-05 | **Retrieve appointments.** A user can fetch one appointment by ID and list a customer's appointments, newest first. | Must | BR-03 |
| FR-06 | **Alternatives on conflict.** When the desired time cannot be served, the response includes up to 3 bookable alternatives closest to the desired time, searched over the next 7 days. | Should | BR-02 |
| FR-07 | **Cancel appointment.** The owning customer can cancel a `CONFIRMED` appointment before it starts. The technician and bay become available again at once. Cancelling twice is a no-op. | Should | BR-03, BR-04 |
| FR-08 | **Idempotent booking.** Booking requires an `Idempotency-Key`. A retry with the same key and body returns the original appointment. The same key with a different body is rejected. | Must | BR-03, NFR-05 |
| FR-09 | **Booking validation rules.** The system rejects a request when: (a) any reference is unknown or inactive; (b) the vehicle is not registered to the customer; (c) the start is not on a 15-minute boundary; (d) the start is less than 60 minutes ahead or more than 90 days ahead; (e) the full slot is outside dealership opening hours; or (f) the vehicle already has an overlapping confirmed appointment. | Must | BR-01, BR-02 |
| FR-10 | **Domain events.** Every confirmation and cancellation emits an `appointment.confirmed` or `appointment.cancelled` event, written atomically with the state change. | Could (1.0 writes the outbox; the relay ships in 1.1) | BR-04 |
| FR-11 | Reschedule an appointment in one step. | Won't (1.0) → roadmap 1.1. Workaround: cancel, then rebook. | — |
| FR-12 | Resource blocks: technician leave and bay maintenance windows. | Won't (1.0) → roadmap 1.1. Workaround: mark the resource inactive. | — |
| FR-13 | Customer chooses a specific technician. | Won't (1.0) — A-11 | — |
| FR-14 | Reference-data administration UI. | Won't (1.0) — data is mastered upstream (A-03) | — |

### 3.1 Acceptance criteria (Given / When / Then)

**FR-01 Book appointment**
1. **Given** vehicle VEH-5001 belongs to CUS-1001 and SVC-PERIODIC lasts 180 min, **when** CUS-1001 books it at DLR-HYD-01 for Tue 10:00 local, **then** the response is `201` with `start_time` 10:00, `end_time` 13:00, status `CONFIRMED`, and a `Location` header.
2. **Given** an unknown dealership, service type, customer or vehicle, **when** a booking is attempted, **then** the response is `422` with code `UNKNOWN_DEALERSHIP`, `UNKNOWN_SERVICE_TYPE`, `UNKNOWN_CUSTOMER` or `UNKNOWN_VEHICLE`.

**FR-02 Real-time resource check**
1. **Given** only one technician holds `EV_HIGH_VOLTAGE` and they are booked 10:00–11:30, **when** a second EV job is requested at 10:00 or 11:15, **then** it is rejected with `409 SLOT_UNAVAILABLE`. **When** it is requested at 11:30 (back-to-back), **then** it succeeds.
2. **Given** two alignment-qualified technicians but one alignment-rig bay, **when** two overlapping alignment jobs are requested, **then** the second is rejected: the bay is the binding constraint.
3. **Given** the dealership is open until 18:00 but the only qualified technician's shift ends at 17:00, **when** a 90-minute job is requested at 16:00, **then** it is rejected.
4. **Given** 20 concurrent requests for the last qualified technician at the same time, **then** exactly 1 succeeds and 19 receive `409`. This holds both in memory and on PostgreSQL.
5. Inactive bays and technicians, and those of other dealerships, are never allocated.

**FR-03 Confirmed appointment record**
1. **Given** a successful booking, **when** it is read back, **then** every field matches, including the technician and bay IDs, and the reference matches `APT-[A-Z2-7]{8}`.
2. **Given** a rejected booking, **then** no appointment row and no outbox event exists.

**FR-04 Availability**: slots lie inside opening hours and the technician shift, and respect lead time and horizon. A slot disappears or shrinks once it is booked.
**FR-05 Retrieve**: an unknown ID returns `404 APPOINTMENT_NOT_FOUND`. A customer list is ordered by `start_time` descending.
**FR-06 Alternatives**: the `409` body contains `alternatives[]` (at most 3) sorted by start time. These are the slots nearest to the requested start.
**FR-07 Cancel**: once cancelled, the same slot can be booked by someone else. Cancelling another customer's appointment returns `404`. Cancelling at or after the start returns `409 CANCELLATION_WINDOW_CLOSED`.
**FR-08 Idempotency**: a replay returns `200` with `Idempotent-Replayed: true` and an identical body, and creates exactly one row and one event. A different body with the same key returns `409 IDEMPOTENCY_KEY_REUSED`. A missing key returns `400 IDEMPOTENCY_KEY_REQUIRED`.
**FR-09 Validation**: each rule (a)–(f) has a dedicated automated test and error code (see the OpenAPI spec).
**FR-10 Events**: each committed confirmation or cancellation adds exactly one outbox row with the payload defined in `04-design/events/`.

## 4. Non-functional requirements

Targets apply to production at the design load in `capacity-estimation_v1.0.md`: 50 bookings/s and
600 requests/s in total. Latency is measured server-side at the ingress and excludes client network time.

| ID | Category | Requirement / metric | Target | How verified |
|---|---|---|---|---|
| NFR-01 | Availability | Monthly success ratio of booking, availability and retrieve APIs (non-5xx) | **≥ 99.9 %** (≈ 43 min/month error budget) | SLO dashboard (`05-operations/slos_v1.0.md`) |
| NFR-02 | Latency | p95 / p99 server latency | Booking **p95 ≤ 500 ms**, p99 ≤ 1 s; availability **p95 ≤ 300 ms**; get/list **p95 ≤ 200 ms** | Load test (test strategy §5), Prometheus histograms |
| NFR-03 | Throughput | Sustained load without breaching NFR-02, error rate < 0.1 % | **50 bookings/s + 550 reads/s for 30 min**; burst ×2 for 5 min | k6 load test in staging before each minor release |
| NFR-04 | Scalability | Horizontal scale with no code change | Stateless API, 3 → 12 pods by HPA; **3,000 dealerships** (2.5× year-1) with no schema change | Architecture review, load test |
| NFR-05 | Data integrity | Double-booking of technician, bay or vehicle | **0**, enforced by the database (exclusion constraints) as well as application checks | Concurrency tests (memory and PostgreSQL), constraint test |
| NFR-06 | Real-time consistency | Staleness of resource state used for a booking decision | **0** — decisions read committed data inside the booking transaction; no cache in the decision path | Design review (ADR-002), tests |
| NFR-07 | Durability / DR | Recovery point / time objectives | **RPO ≤ 5 min, RTO ≤ 1 h**; Multi-AZ database; daily snapshots retained 35 days | Quarterly restore drill (`maintenance_v1.0.md`) |
| NFR-08 | Security | Authentication, transport, hardening | OAuth 2.0 / JWT at the gateway; TLS 1.2+; OWASP ASVS L2; secrets only in a managed vault; container non-root with read-only FS; **0 HIGH/CRITICAL** fixable CVEs at release | CI (Trivy, pip-audit), pen test before go-live |
| NFR-09 | Privacy | PII minimisation and retention | Only display name, VIN and IDs are stored; no PII in logs; appointments retained **3 years**, then anonymised; data stays in India (DPDP Act 2023) | Data-model review, log sampling |
| NFR-10 | Observability | Telemetry coverage | RED metrics for 100 % of routes; JSON logs with `request_id` on 100 % of requests; logs kept 30 days, metrics 13 months; every alert links a runbook section | `/metrics`, alert rules review |
| NFR-11 | Deployability | Release safety | Zero-downtime rolling or canary deploys; **rollback ≤ 10 min**; deploy to production on demand (≥ daily capable) | Pipeline (`.github/workflows/ci-cd.yml`), rollback drill |
| NFR-12 | Maintainability | Code quality gates | Every Must/Should FR has ≥ 1 named automated test (`test_fr_xx_*`); `mypy --strict`, `ruff`, import-layer contract all clean | CI quality job |
| NFR-13 | Interoperability | API contract | OpenAPI 3.1 contract versioned with SemVer; RFC 9457 errors; contract test in CI | `tests/contract/` |
| NFR-14 | Time correctness | Time zones and DST | All instants are timezone-aware and stored in UTC; business rules (hours, shifts) are evaluated in the dealership's IANA time zone | Unit tests, design review |
| NFR-15 | Cost | Production infrastructure at design load | **≤ USD 2,500 / month** (≈ USD 0.0017 per booking at 48k bookings/day) | Monthly cost report |

## 5. Out of scope for 1.0
Payments and deposits; parts reservation; workshop job-card execution (in-progress and completed
states); SMS and email delivery (owned by the notification platform); loaner vehicles; multi-technician jobs.

## 6. Open questions
These are tracked in `assumptions_v1.0.md` §4 with the default adopted for 1.0.

## Revision history

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.0 | 2026-10-15 | Claude Code | Initial baseline: FR-01..FR-14, NFR-01..NFR-15. |
