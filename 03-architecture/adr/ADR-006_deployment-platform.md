# ADR-006: Containers on EKS with RDS PostgreSQL; GitHub Actions; canary with Argo Rollouts

- **Status:** Accepted. Registry choice amended by ADR-008 (ECR instead of GHCR)
- **Date:** 2026-10-15
- **Requirements:** NFR-01, NFR-04, NFR-07, NFR-08, NFR-11, NFR-15; assumptions A-14, A-17

## Context
The organisation's reference template (`quickcart`) already runs on EKS in ap-south-1 with
GitHub Actions. We need zero-downtime deploys, fast rollback and Multi-AZ resilience.

## Decision
- An OCI image built by GitHub Actions, scanned with Trivy, pushed to GHCR with SBOM and provenance, and deployed **by digest**.
- Kustomize base plus overlays (staging, production). Production uses an **Argo Rollouts** canary
  (10 % → 50 % → 100 %) with automated analysis of 5xx rate and p95 latency. Failed analysis aborts and rolls back.
- Migrations run as a pre-deploy Kubernetes Job (Flyway), forward-only and backward-compatible
  (expand/contract), so the previous image keeps working during rollout and rollback.
- RDS PostgreSQL 16 Multi-AZ with PITR, provisioned by Terraform.

## Alternatives considered
| Option | Pros | Cons | Why rejected |
|---|---|---|---|
| ECS Fargate | Less to operate | Diverges from the org platform; weaker progressive delivery | Consistency |
| Serverless (Lambda + Aurora Serverless) | Scale to zero | Connection pooling and cold starts versus a p95 of 500 ms; advisory locks need care | NFR-02 |
| Self-managed PostgreSQL on Kubernetes | Cost | Backups, failover and patching burden | NFR-07 |

## Consequences
Rollback is a revert of the image digest (`kubectl argo rollouts undo`), within 10 minutes (NFR-11).
Schema changes must follow expand/contract (`VERSIONING.md` §5).
