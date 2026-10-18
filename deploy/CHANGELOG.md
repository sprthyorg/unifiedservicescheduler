# Changelog — deploy

## [1.1.0] — 2026-10-17
### Added
- Terraform restructured into modules `database`, `iam-github-oidc` and `cluster-addons`, plus stacks `envs/shared`, `envs/staging` (new; db.t4g.medium single-AZ) and `envs/production` (RDS settings unchanged) — ADR-007.
- GitHub OIDC provider and roles: `uss-ecr-push`, `uss-terraform-plan`, `uss-terraform-apply`, and `uss-deploy-{staging,production}`. Deploy roles get namespace-scoped EKS access entries.
- Cluster add-ons via `helm_release` with EKS Pod Identity: AWS Load Balancer Controller, External Secrets Operator with `ClusterSecretStore aws-secrets-manager`, Argo Rollouts and metrics-server. Each has an `install_*` opt-out.
- DB role bootstrap automated: Terraform generates credentials into `scheduler/<env>/db{,-admin}`; the `db-bootstrap` init container runs `k8s/base/db-bootstrap.sql`, which is idempotent and verified against a non-superuser master on PostgreSQL 16.
- `.github/workflows/infra.yml` + `terraform-apply.yml`: fmt, validate and tflint; per-stack plan as a PR comment; approval-gated apply `shared → staging → production`; per-stack concurrency. `.tflint.hcl` added.
- "Day 0 bootstrap" checklist in `README.md`; new `terraform/README.md`.
### Changed
- Container registry switched from GHCR to ECR (ADR-008). `ci-cd.yml` now pushes only the immutable SHA tag, and logs in via OIDC.
- `ci-cd.yml`: installs the `kubectl argo-rollouts` plugin v1.7.2 before the canary step; ignores `deploy/terraform/**`; shell variables quoted (actionlint clean).
- Kubernetes: the namespace is now created by Terraform (`base/namespace.yaml` removed). ExternalSecrets read per-environment paths (`scheduler/production/…`, with the staging overlay rewriting to `scheduler/staging/…`). A third ExternalSecret `scheduler-bootstrap-secrets` was added.
### Removed
- Manual "One-time database bootstrap" SQL from `README.md`.

## [1.0.1] — 2026-10-15
### Added
- `LOCAL-TESTING.md` local deployment and test guide (USS-DEP-001).
- `local-deploy-and-test.sh` + root `Makefile` (`make verify`, `make verify-all`): one-command deploy, readiness wait, smoke test, DB integrity check and optional full suite; PASS/FAIL exit code, log in `reports/`.
- `make docker-test` / `docker-test.sh`: all suites run inside Docker on an isolated throwaway stack (`docker-compose.test.yml`, `docker/test.Dockerfile`, `docker/run-tests.sh`); JUnit reports; PASS/FAIL exit code; full cleanup.
- `local-smoke-test.sh`: 16-check end-to-end smoke test, safe to re-run; verified against Docker Compose and in-memory modes.

## [1.0.0] — 2026-10-15
### Added
- `docker-compose.yml` (PostgreSQL + migrations + API), verified locally on 2026-10-15.
- Kustomize base (Deployment, Service, HPA 3–12, PDB, NetworkPolicy, Ingress, ExternalSecrets, Flyway Job) and overlays for staging and production (Argo Rollouts canary plus analysis).
- Terraform outline for production RDS PostgreSQL 16 Multi-AZ.
- Prometheus alert rules mapped to runbook sections.
