# Phase prompts (v1.0.0)

Run these in order. Each prompt names its inputs and required outputs, so one phase can be
regenerated and reviewed at a time. Always prepend `00-ai-instructions/CLAUDE.md`.

| # | Phase | Inputs | Outputs |
|---|---|---|---|
| 01 | Analyse scenario | Scenario text | `01-requirements/business-scenario_vX.Y.md`, `requirements_vX.Y.md`, `assumptions_vX.Y.md` |
| 02 | Estimate capacity | Requirements, A-02 | `capacity-estimation_vX.Y.md` |
| 03 | Plan delivery | 01–02 | `02-planning/*` |
| 04 | Design architecture | 01–03 | `03-architecture/architecture_vX.Y.md`, ADRs, diagrams |
| 05 | Detailed design | 04 | OpenAPI, data model, sequences, event schemas |
| 06 | Implement service | 05 | `services/scheduler-service/**` with `test_fr_xx_*` tests |
| 07 | Deployment | 06 | `deploy/**`, `.github/workflows/**` |
| 08 | Operations | 01, 07 | `05-operations/*`, alert rules |
| 09 | Release | all | traceability matrix, `releases/vX.Y.Z/*`, CHANGELOGs |

## 01 — Analyse scenario
> Read the scenario verbatim. Give business requirements IDs (BR-xx). Derive testable functional
> requirements (FR-xx) with MoSCoW priority and Given/When/Then acceptance criteria. Derive NFRs
> (NFR-xx), each with a **number** and a verification method. List every gap as a numbered assumption
> (A-xx) with its rationale and impacts. Record constraints, dependencies and open questions, with
> the default adopted.

## 02 — Estimate capacity
> From A-02, compute appointments per day, peak bookings per second, the request mix, storage over
> the retention period, lock contention and compute. Derive the design targets used by NFR-02/03/04/15.

## 03 — Plan delivery
> Produce milestones with exit criteria and owners, a backlog of user stories mapped to FRs, a RAID
> log (top risks with mitigations), and a test strategy that maps every FR to a test level.

## 04 — Design architecture
> Produce C4 context and container views, components, the deployment view and cross-cutting concerns.
> Write one ADR per non-obvious decision (concurrency control, allocation policy, time model, events,
> platform), each naming the alternatives it rejects.

## 05 — Detailed design
> Write OpenAPI 3.1 (every endpoint lists its errors and idempotency), the data model (every table lists
> its constraints and indexes), sequence diagrams for booking and cancellation, and JSON schemas for events.

## 06 — Implement service
> Implement the design in Python 3.12 / FastAPI / PostgreSQL with layering api → services → domain ←
> repositories, an in-memory adapter for tests, one test per FR, a concurrency test and PostgreSQL
> integration tests. Run all quality gates and report the results honestly.

## 07 — Deployment
> Produce a Dockerfile (non-root, slim), Compose for local use, a Kustomize base and overlays, a migration
> Job ordered before rollout, a canary with automated analysis, Terraform for the database, and CI/CD
> with scan and approval gates. Document rollback.

## 08 — Operations
> Produce SLOs with burn-rate alerts, the metrics and log catalogue, a runbook section per alert,
> maintenance tasks, backup and restore, and DR scenarios with expected recovery times.

## 09 — Release
> Update the traceability matrix (forward and backward), CHANGELOGs, the release manifest pinning all
> artefact versions, release notes, test evidence and an approvals checklist.
