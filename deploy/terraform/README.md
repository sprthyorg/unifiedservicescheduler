# Terraform — Unified Service Scheduler infrastructure

Design: ADR-007 (Day-0 automation) and ADR-008 (ECR). Pipeline: `.github/workflows/infra.yml`.
First-time setup: `deploy/README.md` → "Day 0 bootstrap".

```
deploy/terraform/
├── modules/
│   ├── database/          RDS PostgreSQL 16, KMS, SG, generated passwords → secrets scheduler/<env>/db{,-admin}
│   ├── iam-github-oidc/   GitHub OIDC provider (optional) + roles with EKS access entries
│   └── cluster-addons/    AWS LB Controller, External Secrets + ClusterSecretStore, Argo Rollouts, metrics-server
└── envs/
    ├── shared/            account level: OIDC provider, ECR repo, roles uss-ecr-push / uss-terraform-plan / uss-terraform-apply
    ├── staging/           db.t4g.medium single-AZ, add-ons, namespace scheduler-staging, role uss-deploy-staging
    └── production/        db.r6g.large Multi-AZ, PITR 35 d, add-ons, namespace scheduler, role uss-deploy-production
```

| Stack | State key | Applied by | Order |
|---|---|---|---|
| shared | `unified-service-scheduler/shared.tfstate` | admin (first time), then `infra.yml` (env `infra-shared`) | 1 |
| staging | `unified-service-scheduler/staging.tfstate` | `infra.yml` (env `infra-staging`) | 2 |
| production | `unified-service-scheduler/production.tfstate` | `infra.yml` (env `infra-production`) | 3 |

## Outputs → GitHub variables

| GitHub variable | Command |
|---|---|
| `ECR_REGISTRY` | `terraform -chdir=envs/shared output -raw ecr_registry` |
| `ECR_PUSH_ROLE_ARN` | `terraform -chdir=envs/shared output -raw ecr_push_role_arn` |
| `TF_PLAN_ROLE_ARN` | `terraform -chdir=envs/shared output -raw terraform_plan_role_arn` |
| `TF_APPLY_ROLE_ARN` | `terraform -chdir=envs/shared output -raw terraform_apply_role_arn` |
| `DEPLOY_ROLE_ARN` | `terraform -chdir=envs/staging output -raw deploy_role_arn` |
| `DEPLOY_ROLE_ARN_PROD` | `terraform -chdir=envs/production output -raw deploy_role_arn` |

## Local checks (no AWS account needed)

```bash
terraform fmt -check -recursive deploy/terraform
for e in shared staging production; do terraform -chdir=deploy/terraform/envs/$e init -backend=false && terraform -chdir=deploy/terraform/envs/$e validate; done
```

## Platform team already runs an add-on?
Set the matching `install_*` variable to `false` on `module "cluster_addons"` in the environment stack
(ADR-007 §2). The manifests only need the CRDs and the `ClusterSecretStore` name `aws-secrets-manager`.

## Security notes
- State contains generated DB passwords. Keep the state bucket encrypted, versioned and limited to the plan and apply roles.
- `uss-terraform-apply` has `AdministratorAccess`, and only approval-gated `infra-*` environments can assume it. Follow-up: add a permissions boundary.
