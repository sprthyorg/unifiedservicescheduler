# Deployment

**Running it on your machine?** Follow [`LOCAL-TESTING.md`](LOCAL-TESTING.md) for step-by-step deployment, the smoke test and manual test cases.

| Target | How | Notes |
|---|---|---|
| Local, in-memory | `cd services/scheduler-service && APP_SEED_DEMO_DATA=true uvicorn app.main:app --reload` | No database; demo data seeded |
| Local, full stack | `docker compose -f deploy/docker-compose.yml up --build` | PostgreSQL 16 + migrations + API on :8000 |
| Staging / production (app) | GitHub Actions `.github/workflows/ci-cd.yml` | Kustomize overlays in `deploy/k8s/overlays/*`; images in ECR (ADR-008) |
| Staging / production (infrastructure) | GitHub Actions `.github/workflows/infra.yml` | Terraform stacks in `deploy/terraform/envs/*` (ADR-007) |

## Pipeline order (each deploy)
1. **Quality:** lint, types, import contract, unit, API and contract tests, dependency audit.
2. **Integration:** PostgreSQL 16 service container, all migrations, `pytest -m integration`.
3. **Build:** image, Trivy scan (fails on HIGH/CRITICAL), push to ECR (immutable SHA tag) with SBOM and provenance.
4. **Staging:**
   - delete the old migrate Job, then apply everything except the API workload (`-l 'app.kubernetes.io/component!=api'`);
   - wait for `job/scheduler-db-migrate` (init `db-bootstrap` → copy migrations → Flyway);
   - apply the API workload (`-l app.kubernetes.io/component=api`);
   - wait for the rollout, then run the smoke test.
5. **Production (manual approval):** same order. Argo Rollouts canary 10 % → 50 % → 100 %, with analysis on 5xx rate and p95.

## Rollback (NFR-11: ≤ 10 min)
- **During a canary:** analysis failure aborts automatically, and traffic returns to the stable ReplicaSet.
- **After promotion:** run `kubectl argo rollouts undo scheduler-api -n scheduler`, or re-run the pipeline for the previous digest from `environments/production/versions.yaml`.
- **Schema:** migrations are forward-only and backward-compatible, so the previous image runs on the new schema. Never roll a schema back. Fix forward with `V00N+1`.

## Day 0 bootstrap (once per AWS account)

Everything else is created by Terraform (`deploy/terraform/`, ADR-007) and the pipelines.
Only the steps marked **manual** need a human.

| # | Step | How | Who |
|---|---|---|---|
| 1 | **Manual:** S3 state bucket `ORG-terraform-state` (versioned, KMS-encrypted, access limited to the Terraform roles) and DynamoDB lock table `terraform-locks` | AWS console/CLI, or the org's account-vending baseline | Cloud platform |
| 2 | Prerequisite: VPC, subnets and EKS clusters `ownership-staging` / `ownership-prod`. The network state must exist at `platform/network*.tfstate` with outputs `vpc_id`, `data_subnet_ids`, `eks_node_security_group_id`. Node groups need `AmazonEC2ContainerRegistryReadOnly` | Platform team | Platform |
| 3 | **Manual, once:** first `terraform apply` of `envs/shared` (OIDC provider, ECR repo, CI roles, EKS access for the Terraform roles), run by an account admin, because it creates the roles the pipeline assumes | `cd deploy/terraform/envs/shared && terraform init && terraform apply` | Account admin |
| 4 | **Manual:** GitHub settings | Repository **variables**: `ECR_REGISTRY`, `ECR_PUSH_ROLE_ARN`, `TF_PLAN_ROLE_ARN`, `TF_APPLY_ROLE_ARN` (from `terraform output` of `envs/shared`). **Environments**: `infra-shared`, `infra-staging`, `infra-production`, `staging`, `production`, with required reviewers on `infra-*` and `production`. **Secret**: `STAGING_SMOKE_TOKEN` | Repo admin |
| 5 | Staging and production infrastructure: RDS + generated credentials, add-ons (Load Balancer Controller, External Secrets + `ClusterSecretStore`, Argo Rollouts, metrics-server), namespace, deploy role | Merge to `main` → `infra.yml` applies `shared → staging → production` after approvals | Pipeline |
| 6 | **Manual:** set `DEPLOY_ROLE_ARN` / `DEPLOY_ROLE_ARN_PROD` repository variables | `terraform output -raw deploy_role_arn` in `envs/staging` / `envs/production` | Repo admin |
| 7 | Database roles `scheduler_owner` / `scheduler_app` and their grants | Automatic: the `db-bootstrap` init container of `job/scheduler-db-migrate` runs `deploy/k8s/base/db-bootstrap.sql` on every deploy (idempotent) | Pipeline |
| 8 | **Manual:** DNS `api.scheduler.example` / `api.staging.scheduler.example` → ALB, ACM certificate, API-gateway route (D-03) | DNS / gateway teams | Platform |

After step 8, every merge to `main` runs `ci-cd.yml` end to end without manual steps. Production
still waits for the approval gate.

**Password rotation:** `terraform apply -replace=module.database.random_password.app` (or `.owner`)
in the environment stack, then redeploy. The bootstrap step updates the role password, and External
Secrets refreshes the Kubernetes secrets within 1 h; restart the pods to pick them up immediately.

## Demo seed
`V002__seed_demo_reference_data.sql` runs only where `APPLY_DEMO_SEED=true` (staging overlay).
In production, reference data comes from the DMS and CRM ETL (A-03).
