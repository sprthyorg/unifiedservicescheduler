# Changelog — Unified Service Scheduler (system)

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: `VERSIONING.md`.
Per-area detail is in each folder's `CHANGELOG.md`.

## [Unreleased]
- System design document `03-architecture/system-design_v1.0.md` with architectural plan (USS-SDD-001).
- Documentation now names **Amazon ECR** as the container registry (GHCR retired by ADR-008): `architecture_v1.1.md` (+ `c4-container_v1.1.mmd`), `VERSIONING.md`, `releases/v1.0.0/release-manifest.yaml`.
- Day-0 infrastructure automation (deploy 1.1.0, ADR-007/008): Terraform modules and stacks for shared/staging/production, GitHub OIDC roles, cluster add-ons, automated DB role bootstrap, `infra.yml` pipeline, ECR registry. Only the state bucket, the first `envs/shared` apply, GitHub settings and DNS/gateway remain manual.
- Planned 1.1.0: outbox relay and notifications (FR-10), reschedule (FR-11), resource blocks (FR-12), OpenTelemetry.

## [1.0.0] — 2026-10-15 (release candidate: approvals pending)
### Added
- Requirements baseline v1.0: BR-01..04, FR-01..14, NFR-01..15, assumptions A-01..19, capacity estimate, traceability matrix.
- Planning: roadmap M0–M4, backlog US-01..15, RAID log, test strategy.
- Architecture 1.0.0 and ADR-001..006.
- Design: OpenAPI 1.0.0, data model (schema V001), sequences, event schemas v1.
- scheduler-service 1.0.0 (Python/FastAPI/PostgreSQL) with 53 unit/API/contract tests and 4 PostgreSQL integration tests.
- Deployment: Docker Compose, Kubernetes (Kustomize, Argo Rollouts), Terraform outline, GitHub Actions CI/CD.
- Operations: SLOs, monitoring, runbook RB-01..06, maintenance and DR.
