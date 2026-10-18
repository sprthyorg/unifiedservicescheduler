# Test evidence — release 1.0.0

Executed 2026-10-15 on the generator's workstation (macOS, Python 3.14.6 venv, Docker 29.6.1).
CI re-runs the same suites on Python 3.12 (the production runtime) for every commit.

| Gate | Command | Result |
|---|---|---|
| Lint | `ruff check app tests` | ✅ All checks passed |
| Format | `ruff format --check app tests` | ✅ 30 files formatted |
| Types | `mypy app` (strict) | ✅ No issues in 20 source files |
| Layering | `lint-imports` | ✅ 1 contract kept, 0 broken |
| Unit + use-case + API + contract | `pytest` | ✅ **53 passed** |
| PostgreSQL 16 integration | `APP_TEST_DATABASE_URL=… pytest -m integration` | ✅ **4 passed** (migrations, round trip, 10-connection race, exclusion constraint with the app bypassed) |
| Dependency audit | `pip-audit -r requirements.txt` | ✅ No known vulnerabilities |
| Manifests | `kubectl kustomize deploy/k8s/{base,overlays/staging,overlays/production}` | ✅ All render |
| Local end-to-end | `docker compose -f deploy/docker-compose.yml up --build` + curl | ✅ book 201 → replay 200 (`Idempotent-Replayed`) → conflict 409 with 3 alternatives → cancel 200 → rebook 201; 3 outbox rows |

## Latency baseline (not a load test)
Single sequential client against the Compose stack (API + PostgreSQL 16 in Docker):

| Operation | n | p50 | p95 | p99 | NFR-02 target (p95) |
|---|---|---|---|---|---|
| `GET /v1/availability` | 300 | 1.6 ms | 2.5 ms | 3.7 ms | ≤ 300 ms |
| `POST /v1/appointments` (201 and 409 mixed) | 168 | 1.7 ms | 2.8 ms | — | ≤ 500 ms |

## Not yet executed (required before production go-live)
| Gate | Requirement | When |
|---|---|---|
| Trivy image scan | NFR-08 | First CI run |
| k6 load test at design load | NFR-02, NFR-03 | M1 (staging) |
| Restore drill | NFR-07 | Before M2 |
| Rollback drill | NFR-11 | Before M2 |
| Penetration test | NFR-08 | Before M2 |
