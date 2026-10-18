# AI Assistant Instructions — Unified Service Scheduler

Standing instructions for any AI coding or design assistant working in this repository.
Version 1.0.0 (2026-10-15). Read this file before every task.

## 1. Context
- Product: an appointment scheduler that books vehicle service by allocating a **qualified
  technician** and a **compatible service bay** for the **entire** service duration (Scenario A, Ownership domain).
- Source of truth for *what*: `01-requirements/` (latest `_vX.Y` files). For *why*: `03-architecture/adr/`.
  For *how*: `04-design/`. Never contradict these silently. If a change needs to, update the
  document (new version) or write a new ADR in the same change, and record a CR for requirement changes.

## 2. How to work
1. **Restate the task** in one or two lines and name the requirement IDs it touches (FR-xx, NFR-xx, A-xx).
2. **Read before writing.** Open the relevant design doc and the existing code first.
3. **Plan small.** Propose the smallest change that satisfies the requirement and list the files you will touch.
4. **Write the test first** (or alongside it). Tests are named `test_fr_xx_<behaviour>` / `test_nfr_xx_<behaviour>`.
5. **Implement**, keeping to the layering rules below.
6. **Verify**: run `pytest`, `pytest -m integration` (when SQL changed), `ruff check`, `mypy app` and `lint-imports`. Do not claim done otherwise.
7. **Update traceability** (`01-requirements/traceability-matrix_vX.Y.csv`, then regenerate the `.md`) and the relevant `CHANGELOG.md`.
8. **Summarise**: what changed, which requirements, the version impact (`VERSIONING.md`), and follow-ups.

## 3. Architecture rules (enforced in review and CI)
- Layering: `api → services → domain ← repositories`. `domain` imports nothing from FastAPI, Pydantic or psycopg (import-linter).
- **Every booking decision runs inside one transaction after `uow.lock_dealership()`** (ADR-002). Never add a write path to `appointments` that skips it.
- Never weaken or drop the exclusion constraints in `V001`. They are the last line of defence for NFR-05.
- No cache in the booking decision path (NFR-06). Availability may be cached only if it stays advisory.
- Allocation policy lives only in `app/domain/allocation.py::choose` (ADR-003).
- State changes write an outbox event in the same transaction (ADR-004).
- Booking requires `Idempotency-Key` (FR-08).
- Instants are timezone-aware and stored in UTC. Business rules use the dealership's IANA zone (NFR-14).
- Errors are RFC 9457 problem+json with a stable `code`. New codes go into the OpenAPI document.

## 4. Code conventions
- Python 3.12, FastAPI, Pydantic v2, psycopg 3, type hints everywhere, `mypy --strict`.
- Format with `ruff format` and lint with `ruff check` (line length 120).
- Configuration only via `APP_*` environment variables (`app/config.py`). Booking policy values are config, not constants.
- Structured JSON logs. Include `request_id`, `appointment_id` and `dealership_id` where available. Never log names, phone numbers or VINs.
- No secrets, tokens or real customer data in code, tests, fixtures or prompts.

## 5. Boundaries: ask a human first
- Any migration that drops, renames or narrows a column or constraint.
- Any change to the API contract (`openapi_*.yaml`). It needs a version bump.
- Anything touching authentication, authorisation, PII, retention or the exclusion constraints.
- Adding an external dependency or cloud service.
- Changing assumptions A-01..A-19.

## 6. Definition of done
- [ ] Requirement IDs listed in the commit and PR description
- [ ] Tests added or updated and passing (unit, API, contract; integration if SQL changed)
- [ ] Traceability matrix and CHANGELOGs updated; versions bumped per `VERSIONING.md`
- [ ] Docs updated (design, ADR, runbook) where behaviour changed
- [ ] No new lint, type or import-contract errors
- [ ] New code paths emit logs and metrics consistent with `05-operations/monitoring_v1.0.md`
- [ ] AI-generated code reviewed by a human (`AI-PROVENANCE.md`)
