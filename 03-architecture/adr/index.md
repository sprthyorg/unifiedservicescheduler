# ADR index

| ADR | Title | Status | Requirements |
|---|---|---|---|
| [ADR-001](ADR-001_single-scheduler-service.md) | One scheduler service owning its own PostgreSQL database | Accepted | FR-01..10, NFR-04/05/15 |
| [ADR-002](ADR-002_concurrency-control.md) | Per-dealership advisory lock plus exclusion constraints | Accepted | FR-02, FR-08, NFR-05/06 |
| [ADR-003](ADR-003_allocation-policy.md) | System allocates resources: least-loaded technician, best-fit bay | Accepted | FR-02, FR-03, FR-13 |
| [ADR-004](ADR-004_transactional-outbox.md) | Transactional outbox for appointment events | Accepted | FR-10 |
| [ADR-005](ADR-005_interval-time-model.md) | Continuous intervals with aligned start times | Accepted | FR-02, FR-04, NFR-14 |
| [ADR-006](ADR-006_deployment-platform.md) | EKS + RDS, GitHub Actions, Argo Rollouts canary | Accepted (registry amended by ADR-008) | NFR-01/04/07/08/11/15 |
| [ADR-007](ADR-007_day0-infrastructure-automation.md) | Day-0 infrastructure in Terraform: modules, cluster add-ons, DB role bootstrap, infra pipeline | Accepted | NFR-07/08/11 |
| [ADR-008](ADR-008_container-registry-ecr.md) | Amazon ECR as the container registry (amends ADR-006) | Accepted | NFR-08/11 |

ADRs are immutable once accepted. To change a decision, write a new ADR that supersedes the old one
and set the old one's status to `Superseded by ADR-NNN`.
