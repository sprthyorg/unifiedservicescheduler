# Unified Service Scheduler — Release 1.0.0

An appointment scheduler that replaces manual booking at dealerships (Scenario A, Ownership domain).
A booking is confirmed only when a **qualified technician** and a **compatible service bay** are both
free for the **entire** service duration. The result is a persistent appointment linking
customer, vehicle, technician and bay.

The repository follows the phase-by-phase structure of the organisation's template:
requirements → planning → architecture → design → code → deployment → operations. Every artefact
is **versioned** (`VERSIONING.md`) and **traced** to requirement IDs.

## Project map

| Phase | Folder | Key artefacts (v1.0) |
|---|---|---|
| 0. AI instructions | `00-ai-instructions/` | `CLAUDE.md`, phase prompts v1.0.0, run record |
| 1. Requirements | `01-requirements/` | Scenario (BR-01..04), **FR-01..14**, **NFR-01..15 with numeric targets**, **assumptions A-01..19**, capacity estimate, **traceability matrix** (CSV + MD), sign-off sheet |
| 2. Planning | `02-planning/` | Roadmap M0–M4, backlog, RAID log, test strategy |
| 3. Architecture | `03-architecture/` | **`system-design_v1.0.md` (start here: end-to-end system design + architectural plan)**, `architecture_v1.1.md` (C4 views), **ADR-001..008** (concurrency control, allocation policy, time model, outbox, platform, Day-0 infrastructure, ECR registry) |
| 4. Design | `04-design/` | OpenAPI 3.1 contract 1.0.0, data model (schema V001), sequences, event schemas v1 |
| 5. Implementation | `services/scheduler-service/` | Python 3.12 / FastAPI / PostgreSQL 16; 53 tests + 4 PostgreSQL integration tests |
| 6. Deployment | `deploy/`, `.github/` | Docker Compose, Kustomize (staging, production canary), Flyway Job, Terraform (shared, staging, production), images in **Amazon ECR**, CI/CD (`ci-cd.yml`, `infra.yml`) |
| 7. Operations | `05-operations/` | SLOs, monitoring, runbook RB-01..06, maintenance and DR |
| Release | `releases/v1.0.0/` | Release notes, manifest, **test evidence**, approvals |

## Quick start

```bash
docker compose -f deploy/docker-compose.yml up --build     # API + PostgreSQL → http://localhost:8000/docs
```

Development: `services/scheduler-service/README.md`.

## How the core requirements are met

| Scenario requirement | How it is met | Proof |
|---|---|---|
| 1. Resource-constrained booking | `POST /v1/appointments` with vehicle, service type, dealership and desired start; duration from the service type | `test_fr_01_*` |
| 2. Real-time availability of bay **and** qualified technician for the entire duration | Inside one transaction under a per-dealership lock, `allocation.choose()` checks skill, shift, capability and `[start, end)` overlap. PostgreSQL exclusion constraints make overlap impossible. | `test_fr_02_*` (incl. 20-thread and 10-connection races), `test_nfr_05_*` |
| 3. Confirmed appointment record | `appointments` row with FKs to customer, vehicle, dealership, service type, technician and bay, plus an outbox event in the same transaction | `test_fr_03_*` |

## AI Collaboration Narrative

This repository was produced by a person directing an AI coding assistant (Claude Code, model
`claude-opus-5-5`). The human set the goal, the scope and every change of direction. The AI
drafted the artefacts, ran the checks, and reported results, including failures. This section
explains how that worked, so a reviewer can judge how much to trust the output.

### 1. Strategy for guiding the AI

**Start from an established shape, not a blank page.** The AI was pointed at the organisation's
existing reference projects (`../quickcart`, `../quickcart-versioned`). It reused their phase layout
(`00-ai-instructions` → `05-operations`), layering, test naming and pipeline structure. The new work
then looked like the rest of the estate instead of a one-off design.

**Turn a three-sentence scenario into explicit, numbered decisions.** The scenario says nothing about
slot sizes, lead times, who may book, time zones or data ownership. Instead of silently choosing, the
AI recorded each gap as a numbered assumption (A-01..A-19 in `01-requirements/assumptions_v1.0.md`),
with its rationale and the requirements it affects. A reviewer can overturn any of them without
reading code; changing one is a config or CR change, not a hunt through code.

**Make requirements the thread through everything.** The scenario's three core requirements became
BR-01..03, then testable FRs with Given/When/Then criteria, and NFRs with numbers (for example booking
p95 ≤ 500 ms, zero double-bookings). Every ADR, endpoint, table, module and test cites those IDs, and
`01-requirements/traceability-matrix_v1.1.csv` ties them together. That gave both the AI and the
reviewer one question to ask of any artefact: *which requirement is this for?*

**Write standing rules down.** `00-ai-instructions/CLAUDE.md` holds the rules any assistant must follow:
- work as restate → read → plan → test → implement → verify;
- respect the layer boundaries;
- never write to `appointments` outside the per-dealership lock, and never weaken the exclusion constraints;
- stop and ask a human before touching auth, PII, API contracts or destructive migrations.

The phase prompts (`prompts/phase-prompts_v1.0.0.md`) make each phase repeatable on its own.

**Decide the hard part first and make it explicit.** The real risk in this domain is double-booking
under concurrency, not throughput (capacity estimate §4). ADR-002 therefore fixed the approach before any
code existed. A per-dealership advisory lock serialises decisions, and PostgreSQL exclusion constraints
reject overlaps even if application logic is wrong.

**Iterate in small, human-directed steps.** After the first end-to-end delivery, the human steered
the next increments, each a separate request:
- local deployment instructions → one-command automated testing;
- fully containerised testing;
- closing the Day-0 infrastructure gaps (ADR-007);
- switching the documented registry from GHCR to ECR (ADR-008).

Each increment was verified before the next began.

### 2. Process for verifying and refining the output

Nothing was reported as done until it had been executed. Each layer of evidence was added only after
the one below it passed:

| Level | What was run | What it proves |
|---|---|---|
| Static | `ruff`, `ruff format`, `mypy --strict`, `lint-imports` | Style, types, and that the domain layer stays framework-free |
| Domain and use case | Allocation-rule unit tests and use-case tests, including a 20-thread booking race. Across all levels, 40 tests are named `test_fr_xx_*` | Every in-scope FR has an automated test |
| API and contract | HTTP tests; contract tests against `openapi_1.0.0.yaml` and the event JSON schemas | Code and published contract cannot drift apart |
| Real database | 4 integration tests on PostgreSQL 16: a 10-connection race, and an overlapping insert that bypasses the app | The guarantee holds in the database itself, not just in memory |
| Deployed stack | Docker Compose with a 16-check smoke test and a SQL integrity check | The built image works end to end |
| Fully containerised | `make docker-test` on an isolated, throwaway stack | Reproducible with only Docker installed |
| Infrastructure | `terraform fmt`/`validate` (3 stacks), tflint, actionlint, `kubectl kustomize` (3 overlays) | IaC and pipelines are syntactically and structurally sound |

**Refinement was driven by real failures, not by review alone.** Each of these defects was caught by
running something:

| Found by | Defect | Fix |
|---|---|---|
| API test | Appointment times were returned in the caller's offset instead of UTC | `Appointment.confirm` normalises to UTC (A-10) |
| `mypy --strict` | Protocol attributes did not match the adapters; a Pydantic field named `date` shadowed the type | Read-only protocol properties; renamed import |
| Smoke test, run twice | Run-ID keys collided within one second, so the second run replayed the first | Random per-run idempotency keys |
| Failure-path test | The default macOS bash 3.2 crashed on an empty array under `set -u` | Safe array expansion |
| Bootstrap test on PostgreSQL 16 with a non-superuser master, as on RDS | `ALTER ROLE … NOSUPERUSER` is not allowed for that master | Statement removed; rerun and rotation behaviour re-verified |
| Suspicious "pass" | An old password still connected, because the postgres image trusts loopback connections | Re-tested over the container network, where passwords are enforced |
| actionlint | Unquoted shell variables in `ci-cd.yml` | Quoted |

**Every gate was tested for false passes as well as passes.** Failure paths were deliberately
triggered: an unreachable API, a temporary failing test inside the Docker runner, and a stale-password
login. The automation was confirmed to report `RESULT: FAIL` and exit with code 1, not just to print
green ticks.

### 3. How final quality was ensured

- **Correctness at the lowest possible layer.** No double-booking is enforced three times: allocation
  logic, a transaction-scoped lock, and database exclusion constraints. A code defect cannot produce a
  double booking; it surfaces as a `409` and pages on-call (runbook RB-04).
- **Gates that run on every change**, not just once: the same checks are wired into `ci-cd.yml`
  (quality → integration → image scan → staging smoke → approved canary) and `infra.yml` (fmt, validate
  and tflint, a plan comment on PRs, approval-gated apply).
- **Versioned, immutable baselines.** Changes created new versions instead of rewriting history: for
  example `architecture_v1.1.md`, `traceability-matrix_v1.1.csv`, and ADR-008 amending ADR-006. Each
  folder keeps a CHANGELOG, and the release manifest pins every artefact version (`VERSIONING.md`).
- **Least privilege and no stored credentials by design:**
  - GitHub-to-AWS access uses OIDC;
  - the database credentials are generated and split into admin, owner and app roles; the
    app role was verified to be unable to delete rows or change the schema;
  - containers are non-root and read-only.
- **Honest reporting of limits.** Anything that could not be executed locally is listed as *not
  verified*, never as done:
  - Terraform plan and apply against AWS;
  - load test;
  - restore and rollback drills;
  - pen test;
  - the first real CI run.

  See `releases/v1.0.0/test-evidence.md`, the run record
  `00-ai-instructions/ai-runs/2026-10-15_run-001_end-to-end@v1.0.0/run.yaml`, and
  `services/scheduler-service/AI-PROVENANCE.md`.
- **A human has the final say.** AI-generated code and assumptions are treated as a proposal. Release 1.0.0
  stays a *release candidate* until the product owner, engineering, QA, security, privacy and SRE
  approvals in `releases/v1.0.0/approvals.md` are signed. Those approvals include a line-by-line review
  of the AI-generated code.

## Status
Release **1.0.0 is a release candidate**. Approvals in `releases/v1.0.0/approvals.md` and the
requirements sign-off are pending. Items that need a real environment (load test, restore drill,
pen test, Trivy) are listed in `releases/v1.0.0/test-evidence.md`.
