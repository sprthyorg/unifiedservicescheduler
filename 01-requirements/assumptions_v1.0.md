# Assumptions, Constraints, Dependencies and Open Questions

| Field | Value |
|---|---|
| Document ID | USS-ASM-001 |
| Version | 1.0.0 |
| Status | Baselined. Each assumption needs product-owner confirmation (`releases/v1.0/SIGNOFF.md`) |
| Date | 2026-10-15 |
| Author | Claude Code (AI-generated; human review pending) |

The scenario is three sentences long. Everything else needed to build and run the system is
recorded here as an explicit, numbered assumption, so it can be confirmed or overturned without
rereading code. **If an assumption changes, raise a change request and update the requirement,
config value or ADR listed in the "Impacts" column.**

## 1. Assumptions

| ID | Assumption | Rationale | Impacts | Status |
|---|---|---|---|---|
| A-01 | "User" means the **customer** (self-service) or a **service advisor** acting for a customer. Both use the same API; the gateway carries the role. | The scenario says "a user" without defining it. | FR-01, FR-07, NFR-08 | Proposed |
| A-02 | Year-1 scale: **1,200 dealerships**, on average 8 bays and 10 technicians each, about 5 jobs per bay per day, giving **≈ 48,000 appointments per day**. | Typical national OEM network. | `capacity-estimation_v1.0.md`, NFR-03/04/15 | Proposed |
| A-03 | Dealerships, opening hours, bays and capabilities, technicians, skills and shifts are **mastered in the dealer-management system (DMS)**. Customers and vehicles are mastered in **CRM**. The scheduler keeps read-only replicas. The 1.0 sync is a batch ETL into the reference tables; the event-driven sync ships in 1.1. | The scheduler should not become a second master of HR or asset data. | ADR-001, FR-14, data model | Proposed |
| A-04 | Authentication (OAuth 2.0 / OIDC) is done at the **API gateway**. The gateway rejects calls where `customer_id` ≠ token subject unless the role is `service-advisor` and the dealership is in the advisor's scope. | Existing enterprise gateway; keeps the service free of auth code. | NFR-08, OpenAPI `security` | Proposed |
| A-05 | Start times align to **15-minute** boundaries in dealership local time. Config: `APP_SLOT_GRANULARITY_MINUTES`. | Matches how workshops plan; bounds availability computation. | FR-09(c), FR-04 | Proposed |
| A-06 | Minimum lead time is **60 minutes**. Config: `APP_MIN_LEAD_TIME_MINUTES`. | Workshop needs time to prepare. | FR-09(d) | Proposed |
| A-07 | Booking horizon is **90 days**. Config: `APP_BOOKING_HORIZON_DAYS`. | Shift patterns are rarely known further out. | FR-09(d) | Proposed |
| A-08 | Each service type has a **fixed duration**. The technician and bay are held for the whole duration with no extra buffer. | The scenario says "entire service duration". | FR-02, data model | Proposed |
| A-09 | An appointment needs **exactly one technician and one bay**. Shifts and opening hours are weekly templates that do not cross midnight. Leave and maintenance are not modelled in 1.0; a resource is set *inactive* instead (FR-12 is planned for 1.1). | Keeps 1.0 allocation simple and provably correct. | FR-02, FR-12 | Proposed |
| A-10 | Instants are stored in **UTC**. Business rules use the dealership's **IANA time zone**. Appointment responses are in UTC; availability slots carry the local offset. | DST-safe; unambiguous for clients. | NFR-14, API | Proposed |
| A-11 | The **system chooses** the technician and bay. The customer cannot pick a technician in 1.0. | Maximises utilisation; simpler UX. | FR-13, ADR-003 | Proposed |
| A-12 | No payment or deposit is taken at booking. | Not in the scenario. | Scope | Proposed |
| A-13 | SMS, email and push notifications are sent by the existing **notification platform**, which consumes `appointment.*` events. | Reuse the platform. | FR-10, ADR-004 | Proposed |
| A-14 | Single cloud region (**AWS ap-south-1, Mumbai**) with Multi-AZ. All data stays in India. | DPDP Act; latency to users. | NFR-07, NFR-09, ADR-006 | Proposed |
| A-15 | Walk-in and phone bookings are entered by advisors through the same API, so the system holds one schedule. | Replacing manual booking requires a single source of truth. | BR-04 | Proposed |
| A-16 | Customers may cancel any time before the start, with no fee and no approval step. | Not specified; simplest policy. | FR-07 | Proposed |
| A-17 | Stack: **Python 3.12, FastAPI, PostgreSQL 16, Kubernetes (EKS)**. | Matches the organisation's reference template (`quickcart`) and team skills. | ADR-001, ADR-006 | Proposed |
| A-18 | Customer data held by the scheduler is limited to `display_name`. Vehicle data is limited to VIN, make, model and year. | Data minimisation. | NFR-09 | Proposed |
| A-19 | Appointments are kept **3 years** (warranty and service-history needs), then anonymised. Outbox rows are purged 7 days after publication. | Retention policy needs legal confirmation. | NFR-09, `maintenance_v1.0.md` | Proposed — needs Legal |

## 2. Constraints

| ID | Constraint |
|---|---|
| C-01 | Must replace manual booking: at cut-over, existing future bookings are imported once (roadmap M4). After that, the scheduler is the only place bookings are made. |
| C-02 | Data residency in India (DPDP Act 2023). |
| C-03 | Must integrate through the existing API gateway and identity provider. No separate login. |
| C-04 | Production changes go through the protected pipeline with approval (`.github/workflows/ci-cd.yml`). |

## 3. Dependencies

| ID | Dependency | Owner | Needed by | Risk if late |
|---|---|---|---|---|
| D-01 | DMS export of bays, technicians, skills, shifts and hours | DMS team | M2 (pilot) | Pilot cannot start (RAID R-02) |
| D-02 | CRM export of customers and vehicles | CRM team | M2 | Pilot cannot start |
| D-03 | API gateway route and JWT claims (`sub`, `role`, `dealership_scope`) | Platform team | M2 | Booking cannot be secured |
| D-04 | Notification platform subscribes to `appointment.*` | Comms team | M3 (1.1) | Customers receive no confirmations; advisors notify manually in the interim |
| D-05 | AWS account, EKS cluster, RDS PostgreSQL | Cloud platform | M2 | No staging environment |

## 4. Open questions (with the default adopted for 1.0)

| ID | Question | Default adopted | Owner | Due |
|---|---|---|---|---|
| Q-01 | Should advisors be able to override the lead time for walk-ins? | No. Walk-ins are booked ≥ 60 min ahead, or handled off-system until 1.1. | Product owner | Before M2 |
| Q-02 | Is a cleanup or changeover buffer needed between jobs in the same bay? | No buffer (A-08). It can be added per service type without an API change. | Workshop ops | Before M2 |
| Q-03 | Can one job span a lunch break or a shift change between technicians? | No. One technician must cover the whole slot (A-09). | Workshop ops | Before M2 |
| Q-04 | Should customers choose a preferred technician? | No (A-11, FR-13 Won't). | Product owner | 1.1 planning |
| Q-05 | What is the retention period for appointment history? | 3 years, then anonymise (A-19). | Legal | Before go-live |
| Q-06 | Is there a late-cancellation policy or fee? | No (A-16). | Product owner | 1.1 planning |

## Revision history

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.0 | 2026-10-15 | Claude Code | Initial baseline: A-01..A-19, C-01..C-04, D-01..D-05, Q-01..Q-06. |
