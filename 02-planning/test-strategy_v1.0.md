# Test Strategy

| Field | Value |
|---|---|
| Document ID | USS-TST-001 |
| Version | 1.0.0 |
| Date | 2026-10-15 |
| Evidence for 1.0.0 | `releases/v1.0.0/test-evidence.md` |

## 1. Principles
- Every Must and Should FR has at least one automated test named `test_fr_xx_<behaviour>`. NFRs that can be tested use `test_nfr_xx_*` (NFR-12).
- Correctness under concurrency (NFR-05) is tested at two levels: in-memory logic and the real PostgreSQL constraints.
- Tests are deterministic. Time comes from an injected `FakeClock`, never from the wall clock.

## 2. Test levels

| Level | Location | What it proves | Runs in |
|---|---|---|---|
| Domain unit | `tests/test_allocation.py` | Allocation rules: overlap, hours, shift, skill, capability, load balancing, best-fit bay | CI `quality` (every PR) |
| Use case | `tests/test_scheduling_service.py` | FR-01..FR-09 end to end through the service layer on the in-memory adapter, including a 20-thread race | CI `quality` |
| API | `tests/test_api.py` | Status codes, headers, problem+json bodies, metrics, health | CI `quality` |
| Contract | `tests/contract/test_openapi_v1_1_0_0.py` | Running app exposes exactly the operations of `openapi_1.0.0.yaml`; request schemas agree | CI `quality` |
| Integration | `tests/integration/test_postgres.py` (`-m integration`) | Migrations apply; round trip; 10-connection race; exclusion constraint blocks overlap even when the app is bypassed | CI `integration` (PostgreSQL 16 service container) |
| Smoke | CI `deploy-staging` step; `deploy/README.md` | Deployed service books, replays, conflicts and cancels | After each staging deploy |
| Load | k6 script (§5) | NFR-02, NFR-03 | Staging, before each minor release |
| Security | Trivy image scan, pip-audit, ruff `S` rules; external pen test | NFR-08 | CI; pre-go-live |

## 3. Requirement → test mapping
See the "Test" column of `01-requirements/traceability-matrix_v1.0.csv`.

## 4. Entry and exit criteria per release
- **Entry:** requirements baseline signed; contract version bumped if the API changed.
- **Exit:** all automated levels green; zero open Sev-1 or Sev-2 defects; load test meets NFR-02/03; image scan shows 0 HIGH/CRITICAL fixable vulnerabilities; evidence recorded in `releases/vX.Y.Z/test-evidence.md`.

## 5. Load test profile (k6, staging)

| Phase | Duration | Load |
|---|---|---|
| Ramp | 5 min | 0 → 600 RPS (mix from capacity estimate §2) |
| Steady | 30 min | 400 availability + 55 booking + 100 get/list + 45 reference RPS |
| Burst | 5 min | × 2 |
| Pass | | p95 within NFR-02, error rate (5xx) < 0.1 %, **0 overlapping CONFIRMED rows** (SQL check after the run) |

The post-run integrity check (it must return 0):

```sql
SELECT count(*) FROM appointments a JOIN appointments b
  ON a.id < b.id AND a.status = 'CONFIRMED' AND b.status = 'CONFIRMED'
 AND (a.technician_id = b.technician_id OR a.service_bay_id = b.service_bay_id OR a.vehicle_id = b.vehicle_id)
 AND tstzrange(a.start_at, a.end_at) && tstzrange(b.start_at, b.end_at);
```

## 6. Defect severity

| Severity | Definition | Example |
|---|---|---|
| Sev-1 | Data integrity or security breach | Double-booking; another customer's appointment visible |
| Sev-2 | Core journey broken, no workaround | Booking returns 5xx |
| Sev-3 | Degraded, with a workaround | Alternatives missing in a 409 |
| Sev-4 | Cosmetic | Wording in an error `detail` |
