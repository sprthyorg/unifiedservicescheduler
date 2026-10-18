# Maintenance, Backup and Disaster Recovery

| Field | Value |
|---|---|
| Document ID | USS-OPS-004 |
| Version | 1.0.0 |
| Date | 2026-10-15 |
| Requirements | NFR-07, NFR-08, NFR-09 |

## 1. Routine tasks

| ID | Task | Frequency | How | Owner |
|---|---|---|---|---|
| M-01 | Dependency updates (Python packages, base image, `tzdata`) | Monthly, plus emergency CVE patches within 7 days for HIGH and 48 h for CRITICAL | Dependabot PR → full pipeline | Eng |
| M-02 | Reference-data quality report (unknown skills or capabilities, dealerships with no shifts) | Daily | ETL job report | Data |
| M-03 | Outbox purge: `DELETE FROM outbox WHERE published_at < now() - interval '7 days'` (from 1.1, once the relay marks rows published) | Daily | Kubernetes CronJob (1.1) | Eng |
| M-04 | Retention: anonymise appointments where `end_at < now() - interval '3 years'` (A-19) | Monthly | SQL job as `scheduler_owner` | Eng + Privacy |
| M-05 | `VACUUM (ANALYZE)` check and bloat review | Weekly (autovacuum on) | RDS Performance Insights | SRE |
| M-06 | Restore drill (§2) | Quarterly | Runbook below | SRE |
| M-07 | Rollback drill (canary abort and undo in staging) | Each minor release | Pipeline | SRE |
| M-08 | Access review (DB roles, GitHub environments, AWS roles) | Quarterly | Security checklist | Security |
| M-09 | SLO review and error-budget policy | Weekly ops review | Grafana SLO board | SRE + PO |

## 2. Backup and restore

| Item | Setting | Objective |
|---|---|---|
| Automated backups and PITR | 35 days, continuous WAL archiving | **RPO ≤ 5 min** |
| Multi-AZ | Synchronous standby, automatic failover (60–120 s) | AZ loss is covered within the SLO |
| Snapshot copy | Daily snapshot copied to ap-south-2 (Hyderabad), kept 35 days, encrypted with KMS | Region loss: RPO ≤ 24 h (accepted for 1.0) |
| Restore procedure | 1) `aws rds restore-db-instance-to-point-in-time` to a new instance. 2) Validate (row counts, integrity SQL from RB-04). 3) Swap the `scheduler/db` secret endpoint. 4) `kubectl argo rollouts restart`. | **RTO ≤ 1 h** |

Record each restore drill's measured RPO and RTO in `05-operations/CHANGELOG.md`.

## 3. Disaster scenarios

| Scenario | Impact | Response | Expected recovery |
|---|---|---|---|
| One pod or node lost | None | Kubernetes reschedules; PDB keeps ≥ 2 pods | Seconds |
| One AZ lost | Brief errors during DB failover | Multi-AZ failover; topology spread | < 2 min |
| Bad deploy | Errors or latency | Canary auto-abort; `undo` | < 10 min |
| Data corruption (bad ETL or manual SQL) | Wrong schedules | PITR to before the event into a new instance; reconcile appointments created since | < 1 h plus reconciliation |
| Region lost | Full outage | Restore the latest cross-region snapshot in ap-south-2, redeploy through the pipeline | < 8 h (1.0 accepted risk; revisit at M4) |

## 4. Change windows
Normal deploys can happen any time (zero downtime). Database instance-class changes and major
engine upgrades happen after 20:00 IST or on Sunday, when workshops are closed.
