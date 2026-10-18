# ADR-007: Day-0 infrastructure is Terraform-managed in this repo, including cluster add-ons and DB role bootstrap

- **Status:** Accepted
- **Date:** 2026-10-17
- **Requirements:** NFR-07, NFR-08, NFR-11; assumptions A-03, A-14; dependency D-05

## Context
The application pipeline (`ci-cd.yml`) assumed infrastructure that nothing in the repository
created:
- the RDS database for staging;
- the IAM roles GitHub Actions assumes;
- the in-cluster controllers the manifests depend on: the AWS Load Balancer Controller (`Ingress` with
  `ingressClassName: alb`), External Secrets Operator with a `ClusterSecretStore` named
  `aws-secrets-manager`, Argo Rollouts (`Rollout`, `AnalysisTemplate`) and metrics-server (HPA);
- the PostgreSQL roles `scheduler_owner` and `scheduler_app`, which were created by hand-run SQL.

Every one of these was a manual Day-0 step and a source of drift between staging and production.

## Decision
1. **Layout:** reusable modules (`database`, `iam-github-oidc`, `cluster-addons`) composed by three
   root stacks: `envs/shared` (account level), `envs/staging` and `envs/production`. Each stack has its own state file.
2. **Cluster add-ons are installed by this repo** (`modules/cluster-addons`, `helm_release`), using
   EKS Pod Identity for their AWS permissions. Every add-on has an `install_*` toggle, so a platform team
   that already runs one can switch it off without forking the module. The External Secrets
   policy is scoped to `scheduler/*` secrets only.
3. **DB role bootstrap is automated in two halves:**
   - **Terraform** (`modules/database`) generates the admin, owner and app passwords
     (`random_password`) and writes two Secrets Manager secrets:
     - `scheduler/<env>/db-admin`: master credentials, read only by the bootstrap step;
     - `scheduler/<env>/db`: owner and app credentials, plus the ready-made `app_url` and `flyway_jdbc_url`.
   - **In the cluster**, the first init container of the migration Job (`db-bootstrap`) runs an
     idempotent SQL script as the master user. It creates or updates both roles and their grants,
     then Flyway runs as `scheduler_owner`.
   - The bootstrap runs *inside* the VPC because RDS is private: GitHub-hosted runners cannot reach it,
     so the Terraform `postgresql` provider is not an option. It reruns on every deploy, so password
     rotation means "replace `random_password`, apply, redeploy".
4. **Infrastructure pipeline:** `.github/workflows/infra.yml` runs fmt, validate and tflint, and posts a
   plan comment on every PR. Applies on `main` run through approval-gated GitHub environments
   (`infra-staging`, `infra-production`), with per-stack concurrency.
5. **Only these steps remain manual:**
   - the Terraform state bucket and lock table;
   - the **first** `terraform apply` of `envs/shared` by an account administrator, because it
     creates the roles the pipeline itself assumes;
   - GitHub environments, variables and secrets;
   - DNS and the API-gateway route.

## Alternatives considered
| Option | Pros | Cons | Why rejected |
|---|---|---|---|
| Platform team owns all add-ons; this repo only documents them | Clear ownership on a shared cluster | Hidden dependency; the scheduler cannot be stood up from this repo; no review of versions | Kept as an *opt-out* (`install_*` toggles) rather than the default |
| `kubectl apply` add-on manifests from the deploy pipeline | No Terraform for in-cluster objects | Two tools managing infrastructure; no plan or diff; IAM still needs Terraform | Split brain |
| Terraform `postgresql` provider for roles | Pure Terraform | Needs network reach into private subnets (self-hosted runner or bastion) | Network exposure / extra runners |
| RDS-managed master secret (`manage_master_user_password`) | Automatic rotation | Its secret name is generated, so a static `ExternalSecret` cannot reference it | Predictable secret names win for 1.0. Revisit with the ESO `find`-by-tag feature |

## Consequences
- **Terraform state now contains generated passwords.** The state bucket must be KMS-encrypted,
  versioned and restricted to the plan and apply roles. The plan role also needs `secretsmanager:GetSecretValue`
  on `scheduler/*` to refresh secret versions.
- **The PR plan role needs read access to the clusters.** The Helm provider reads release state, so
  the role gets the `AmazonEKSAdminViewPolicy` access entry. The shared stack grants it.
- Staging and production are assumed to share **one AWS account** (separate VPCs and clusters). That is why the GitHub OIDC provider and ECR live in `envs/shared`. If production moves to its own account, run `envs/shared` once per account with `create_provider = true`.
- On a shared cluster, a second consumer of the same add-on must coordinate versions with this repo, or set `install_*` to `false`.
