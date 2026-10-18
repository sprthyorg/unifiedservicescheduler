# Business Scenario — The Unified Service Scheduler

| Field | Value |
|---|---|
| Document ID | USS-BIZ-001 |
| Version | 1.0.0 |
| Status | Baselined |
| Date | 2026-10-15 |
| Owner | Product Owner, Ownership domain (to be named) |
| Author | Claude Code (AI-generated; human review pending) |

## 1. Scenario as given (verbatim)

> **Scenario A: The Unified Service Scheduler**
> - **Domain:** Ownership
> - **Task:** Build an Appointment Scheduler application to replace manual booking systems.
> - **Core Requirements:**
>   1. **Resource Constrained Booking:** Allow a user to request a service appointment for a specific vehicle, service type, and dealership at a desired time.
>   2. **Real-Time Availability Check:** Before confirming, check for the availability of both a ServiceBay and a qualified Technician for the entire service duration.
>   3. **Confirmed Appointment Record:** Upon success, create a persistent Appointment record associating the customer, vehicle, technician, and service bay.

## 2. Business requirements (derived IDs)

| ID | Business requirement | Source |
|---|---|---|
| BR-01 | A user can request a service appointment for a specific vehicle, service type and dealership at a desired time. | Core requirement 1 |
| BR-02 | A booking is confirmed only if a service bay **and** a qualified technician are both free for the **entire** service duration, checked at booking time. | Core requirement 2 |
| BR-03 | A successful booking creates a persistent appointment record linking customer, vehicle, technician and service bay. | Core requirement 3 |
| BR-04 | The application replaces manual booking (phone calls, spreadsheets, paper diaries) at dealerships. | Task statement |

## 3. Problem today (assumed context — see `assumptions_v1.0.md`)

- Bookings are taken by phone and written into per-dealership spreadsheets or diaries.
- Double-booking of bays and technicians happens because nobody checks both resources for the full job length.
- Customers cannot self-serve, and the brand has no network-wide view of service demand.

## 4. Business goals and success measures

| Goal | Measure | Target (12 months after rollout) |
|---|---|---|
| G-1 Eliminate double-booking | Bay or technician conflicts found on the shop floor | 0 caused by the system (NFR-05) |
| G-2 Shift to self-service | Share of bookings made through digital channels | ≥ 60 % |
| G-3 Faster booking | Median time for a customer to get a confirmed slot | < 2 minutes (from ~10 minutes by phone) |
| G-4 Better resource use | Bay utilisation during opening hours | +10 percentage points against the manual baseline |
| G-5 Retire manual tools | Dealerships still on spreadsheets or diaries | 0 after the M4 cut-over (roadmap) |

## 5. Stakeholders

| Stakeholder | Interest |
|---|---|
| Vehicle owner (customer) | Books, views and cancels appointments. |
| Service advisor (dealership) | Books on behalf of walk-in and phone customers; sees the day plan. |
| Workshop manager | Owns bays, technician shifts and skills (in the upstream dealer-management system). |
| Ownership domain product owner | Accountable for scope and sign-off. |
| Platform / SRE team | Runs the service against its SLOs. |
| Security and privacy office | Owns PII handling and compliance with the DPDP Act. |

## Revision history

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.0 | 2026-10-15 | Claude Code | Initial baseline from Scenario A. |
