# Runbook — scheduler-service

| Field | Value |
|---|---|
| Document ID | USS-OPS-003 |
| Version | 1.0.0 |
| Date | 2026-10-15 |
| On-call | Ownership scheduler rota (PagerDuty service `scheduler-service`) |
| Escalation | SRE lead → Engineering lead → Product owner (customer communications) |

Namespace `scheduler` (production) or `scheduler-staging`. Useful commands:
```bash
kubectl -n scheduler get pods -l app=scheduler-api
kubectl -n scheduler logs -l app=scheduler-api --since=15m | jq 'select(.level!="INFO")'
kubectl argo rollouts get rollout scheduler-api -n scheduler
```

## RB-01 5xx spike
1. Check whether a rollout is in progress: `kubectl argo rollouts get rollout scheduler-api -n scheduler`. If so, run `kubectl argo rollouts abort scheduler-api -n scheduler`, then `undo`.
2. Read the error logs: `jq 'select(.status>=500 or .exc)'`. Look for these patterns:
   - `psycopg.OperationalError` / pool timeout → go to RB-05 or RB-06 (database).
   - `ZoneInfoNotFoundError` → bad `timezone` value in the dealership reference data; fix the ETL row (RB-03 step 3).
3. If it is isolated to one dealership, check its reference data (RB-03).
4. Note the error-budget impact in the incident ticket. A post-incident review is required if more than 10 % of the budget was used.

## RB-02 Slow booking or availability
1. Compare p95 by route on Grafana "golden signals".
2. If all routes are slow, check CPU and HPA. Are pods at max (12)? If so, raise `maxReplicas` temporarily and check RDS CPU.
3. If only booking is slow, look for advisory-lock waits: `SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted;`. Sustained waits mean a hot dealership or a slow transaction. Find long transactions in `pg_stat_activity` (`state='idle in transaction'`).
4. If only availability is slow, check the slow-query log for `ix_appointments_dealership_start` usage. Run `ANALYZE appointments;`.

## RB-03 Many SLOT_UNAVAILABLE
This is usually a **reference-data** problem (R-02), not a bug.
1. Find the affected dealerships on the business dashboard (rejection ratio by dealership).
2. For a dealership D:
   ```sql
   SELECT id, active, skills FROM technicians WHERE dealership_id = 'D';
   SELECT * FROM technician_shifts s JOIN technicians t ON t.id = s.technician_id WHERE t.dealership_id = 'D';
   SELECT id, active, capabilities FROM service_bays WHERE dealership_id = 'D';
   SELECT * FROM dealership_hours WHERE dealership_id = 'D';
   ```
   Look for missing shifts, everything inactive, or skill and capability vocabulary that does not match `service_types` (for example `EV-HV` against `EV_HIGH_VOLTAGE`).
3. Fix at the source (DMS or CRM) and re-run the ETL. Do not hand-edit replicas except in an emergency, and record any change in the ticket.
4. If the data is correct, the dealership really is full. Inform the business (capacity).

## RB-04 Exclusion backstop triggered
**Sev-1 candidate.** The database rejected an overlapping booking that the application logic should
have prevented. Customers were protected (they got a 409), but ADR-002's first line of defence failed.
1. Collect the logs around the event (`request_id`, `dealership_id`).
2. Verify integrity. This must return 0:
   ```sql
   SELECT count(*) FROM appointments a JOIN appointments b ON a.id < b.id
    AND a.status='CONFIRMED' AND b.status='CONFIRMED'
    AND (a.technician_id=b.technician_id OR a.service_bay_id=b.service_bay_id OR a.vehicle_id=b.vehicle_id)
    AND tstzrange(a.start_at,a.end_at) && tstzrange(b.start_at,b.end_at);
   ```
3. Check for a code path that writes appointments without `lock_dealership`, or for a manual or ETL write.
4. Open an incident and a post-incident review.

## RB-05 Pods not ready / database unreachable
1. `kubectl -n scheduler describe pod <pod>`: are readiness probes failing on `/health/ready`?
2. Check the RDS status in the console or CLI. During a Multi-AZ failover (60–120 s), pods recover by themselves when the pool reconnects.
3. Check that the secret is present: `kubectl -n scheduler get secret scheduler-secrets`. If a credential was rotated, restart the pods with `kubectl argo rollouts restart scheduler-api -n scheduler`.
4. Check that the NetworkPolicy and RDS security group still allow 5432 from the nodes.

## RB-06 Database capacity
1. On CPU > 80 %, check top statements in Performance Insights. Scale the instance class up (Multi-AZ, so this is a short failover) during low traffic (after 20:00 IST).
2. On free storage < 20 %, autoscaling storage covers up to 500 GB. Check the outbox purge job (maintenance M-03).

## Rollback (all incidents)
Use `kubectl argo rollouts undo scheduler-api -n scheduler` (≤ 10 min, NFR-11). Schema is
forward-only (`deploy/README.md`).
