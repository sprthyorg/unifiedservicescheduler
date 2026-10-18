# ADR-008: Use Amazon ECR as the container registry (amends ADR-006)

- **Status:** Accepted. Amends the registry choice in ADR-006; the rest of ADR-006 stands.
- **Date:** 2026-10-17
- **Requirements:** NFR-08, NFR-11; constraint C-02

## Context
ADR-006 pushed images to GHCR. A private GHCR package needs either a Kubernetes `imagePullSecret`
holding a GitHub token or a public package. A token adds a long-lived credential to every namespace
and creates a dependency on GitHub at pod start-up.

## Decision
Push images to an **ECR repository** (`unified-service-scheduler/scheduler-service`) in
ap-south-1, created by `envs/shared`.
- Tags are **IMMUTABLE**. CI pushes the git SHA tag, and deploys by digest.
- Scan on push is enabled, the repository is KMS-encrypted, and a lifecycle rule keeps the last 50 images.
- GitHub Actions pushes with a dedicated OIDC role (`ECR_PUSH_ROLE_ARN`) that may push only to this repository.
- EKS nodes pull with their node IAM role (`AmazonEC2ContainerRegistryReadOnly`, standard on EKS
  managed node groups), so no pull secret exists anywhere.

## Alternatives considered
| Option | Pros | Cons | Why rejected |
|---|---|---|---|
| GHCR + `imagePullSecret` synced by External Secrets | Keeps ADR-006 | Long-lived GitHub PAT; GitHub outage blocks pod scheduling | Credential and availability risk |
| Public GHCR package | No secret | Exposes the image publicly | Not acceptable for internal code |

## Consequences
- The CI `build` job needs AWS credentials only on `push` to `main`. PR builds still scan locally without pushing.
- The semver tag is no longer pushed on every build, because immutable tags forbid re-tagging. A release workflow will tag `vX.Y.Z` images once per release (follow-up).
- Images stay in the same region as the clusters (C-02).
