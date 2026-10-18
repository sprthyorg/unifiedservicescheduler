# Local Deployment and Testing Guide

| Field | Value |
|---|---|
| Document ID | USS-DEP-001 |
| Version | 1.0.0 |
| Applies to | scheduler-service 1.0.0 |
| Date | 2026-10-15 |

All commands run from the repository root (`unified_service_scheduler/`) unless stated otherwise.

## 0. Prerequisites

| Tool | Needed for | Check |
|---|---|---|
| Docker Desktop (running) | Option A, integration tests | `docker info` |
| Python ≥ 3.12 | Option B, automated tests | `python3 --version` |
| curl | Smoke test, manual calls | `curl --version` |

Port **8000** (API) and **5432** (PostgreSQL) must be free.

---

## Quickest path: deploy and test automatically with one command

```bash
make verify        # deploy → wait for readiness → smoke test → DB integrity check (stack keeps running)
make verify-all    # fresh DB → deploy → smoke + integrity → lint/types → 53 tests → 4 PostgreSQL tests → tear down
```

`make` calls `deploy/local-deploy-and-test.sh`, which you can also run directly with options:

| Option | Effect |
|---|---|
| `--suite smoke` (default) / `--suite all` | Tests run after the deployment |
| `--fresh` | Delete the local database volume first |
| `--down` | Stop the stack and delete its data at the end |
| `--no-build` | Reuse the existing image (faster re-runs) |

What it does, in order:
1. Checks Docker. On macOS it starts Docker Desktop if it isn't running.
2. Runs `docker compose up`.
3. Waits up to 120 s for `/health/ready`, and prints container logs if the API never becomes ready.
4. Runs the 16-check smoke test.
5. Runs an SQL integrity check: zero overlapping confirmed bookings.
6. With `--suite all`, it also runs:
   - lint, types and the import contract
   - unit, API and contract tests
   - integration tests on a throwaway PostgreSQL on port 55432, never the deployed database

It ends with a summary and `RESULT: PASS` or `RESULT: FAIL`, and exits with **0 or 1**, so it can
gate a git hook or a CI job. A full log is saved to `reports/local-test-<timestamp>.log`.

### Everything inside Docker (no local Python needed)

```bash
make docker-test          # or: ./deploy/docker-test.sh
```

This builds and starts a separate, throwaway stack (`deploy/docker-compose.test.yml`, project
`uss-test`). It uses no host ports and no volumes, so it never touches your dev stack or its data:

| Container | Role |
|---|---|
| `postgres` → `migrate` → `api` | The deployed app: the same API image that ships to Kubernetes, schema and demo data |
| `test-db` | Empty PostgreSQL for the integration tests |
| `tests` | Test-runner image (`deploy/docker/test.Dockerfile`). It waits until `api` is ready, then runs `deploy/docker/run-tests.sh` |

The runner executes, in order:
1. ruff
2. mypy
3. import contract
4. 53 unit, API and contract tests
5. 4 PostgreSQL integration tests
6. the 16-check smoke test against `http://api:8000`
7. the database integrity check

It prints a summary and `RESULT: PASS` or `RESULT: FAIL` and exits **0 or 1**. All test containers
and data are then removed, even when a run fails or is interrupted. JUnit XML is written to
`reports/junit-unit.xml` and `reports/junit-integration.xml`. A full run takes about 50 s (longer
on the first image build).

Other shortcuts: `make up`, `make smoke` (against a running stack), `make test` (no Docker),
`make down`, `make reset`, `make help`. Sections 1–5 below cover the same steps by hand.

---

## 1. Deploy

### Option A: full stack with Docker (recommended)

This runs PostgreSQL 16, applies the migrations (schema and demo data), then starts the API, which
is the same image used for Kubernetes.

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

Wait until it is ready (about 10–30 s on the first build):

```bash
curl -s localhost:8000/health/ready
```

Expected: `{"status":"ok"}`. If you see `connection refused`, wait a few seconds and retry. Check
`docker compose -f deploy/docker-compose.yml ps`: `migrate` must show *Exited (0)* and `api` *running*.

### Option B: API only, in-memory (no Docker)

```bash
cd services/scheduler-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
APP_SEED_DEMO_DATA=true uvicorn app.main:app --port 8000
```

Data lives in memory and is lost on restart. Use this mode for quick API exploration.

---

## 2. Automated smoke test (about 5 seconds)

In a second terminal, from the repository root:

```bash
./deploy/local-smoke-test.sh
```

It books, retries, triggers a conflict, validates, reads back, cancels and rebooks against the
running API. It uses next Tuesday as the test date. Expected ending:

```
Result: 16 passed, 0 failed
```

The script cleans up after itself, so it can be re-run at any time.

---

## 3. Manual testing

**Swagger UI:** open <http://localhost:8000/docs>. Every endpoint has *Try it out*.

**Demo data:**
- Dealership `DLR-HYD-01`, Asia/Kolkata, open Mon–Sat 08:00–18:00.
- Technicians:
  - `TEC-001`: GENERAL, 08:00–17:00
  - `TEC-002`: GENERAL + ALIGNMENT, 09:00–18:00
  - `TEC-003`: GENERAL + **EV_HIGH_VOLTAGE**, 08:00–17:00. The only EV technician.
- Bays:
  - `BAY-01`, `BAY-02`: LIFT
  - `BAY-03`: LIFT + ALIGNMENT_RIG
  - `BAY-04`: LIFT + EV_SAFE
- Service types:

  | Service type | Duration | Needs |
  |---|---|---|
  | `SVC-OIL` | 60 min | GENERAL / LIFT |
  | `SVC-PERIODIC` | 180 min | GENERAL / LIFT |
  | `SVC-ALIGN` | 45 min | ALIGNMENT / ALIGNMENT_RIG |
  | `SVC-EV-BATT` | 90 min | EV_HIGH_VOLTAGE / EV_SAFE |

- Customers and vehicles: `CUS-1001` owns `VEH-5001`; `CUS-1002` owns `VEH-5002`.

Pick any **Monday–Saturday date within the next 90 days**, at least 1 hour ahead. Start times must
be on a 15-minute boundary. The examples use `2026-10-20`; replace it with your date.

**a) See free times (FR-04)**
```bash
curl -s "localhost:8000/v1/availability?dealership_id=DLR-HYD-01&service_type_id=SVC-EV-BATT&date=2026-10-20"
```

**b) Book (FR-01..03).** The response is `201`, and the scheduler picks the technician and bay.
```bash
curl -s -X POST localhost:8000/v1/appointments \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-key-0001' \
  -d '{"customer_id":"CUS-1001","vehicle_id":"VEH-5001","dealership_id":"DLR-HYD-01",
       "service_type_id":"SVC-EV-BATT","desired_start_time":"2026-10-20T10:00:00+05:30"}'
```
Expected: `"technician_id":"TEC-003","service_bay_id":"BAY-04"`. Times come back in UTC (`04:30Z` = 10:00 IST).

**c) Retry the same request (FR-08).** Run (b) again unchanged. You get `200` with header
`Idempotent-Replayed: true` (use `curl -i`) and the same `id`. No duplicate is created.

**d) Resource conflict (FR-02, FR-06).** Another customer wants an EV check at the same time. The
only EV technician is busy, so the response is `409 SLOT_UNAVAILABLE` with three nearby `alternatives`.
```bash
curl -s -X POST localhost:8000/v1/appointments \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-key-0002' \
  -d '{"customer_id":"CUS-1002","vehicle_id":"VEH-5002","dealership_id":"DLR-HYD-01",
       "service_type_id":"SVC-EV-BATT","desired_start_time":"2026-10-20T11:00:00+05:30"}'
```
11:00 also fails because the first job runs until 11:30 (the *entire duration* rule). Try `11:30`
with a new key: back-to-back succeeds.

**e) Validation (FR-09).** Each of these returns `422` with a specific `code`:

| Change to the request in (b) | Code |
|---|---|
| `"desired_start_time":"2026-10-20T07:00:00+05:30"` | `OUTSIDE_BUSINESS_HOURS` |
| `"desired_start_time":"2026-10-20T10:10:00+05:30"` | `START_TIME_NOT_ALIGNED` |
| `"vehicle_id":"VEH-5002"` (not CUS-1001's) | `VEHICLE_NOT_OWNED_BY_CUSTOMER` |
| a Sunday date | `OUTSIDE_BUSINESS_HOURS` |

**f) Read and list (FR-05)**
```bash
curl -s localhost:8000/v1/appointments/<id>
curl -s "localhost:8000/v1/appointments?customer_id=CUS-1001"
```

**g) Cancel (FR-07).** This frees TEC-003 and BAY-04 immediately. Retry (d) afterwards with a new key and it succeeds.
```bash
curl -s -X POST localhost:8000/v1/appointments/<id>/cancel \
  -H 'Content-Type: application/json' -d '{"customer_id":"CUS-1001","reason":"changed plans"}'
```

**h) Inspect the database (Option A only)**
```bash
docker compose -f deploy/docker-compose.yml exec postgres psql -U scheduler -c \
  "select reference, technician_id, service_bay_id, start_at, status from appointments order by created_at;"
docker compose -f deploy/docker-compose.yml exec postgres psql -U scheduler -c \
  "select event_type, occurred_at from outbox order by occurred_at;"
```

**i) Logs and metrics**
```bash
docker compose -f deploy/docker-compose.yml logs -f api        # JSON access logs with request_id
curl -s localhost:8000/metrics | grep scheduler_               # business counters
```

---

## 4. Automated test suites

```bash
cd services/scheduler-service
source .venv/bin/activate                     # created in Option B
pytest                                        # 53 unit, API and contract tests (no Docker needed)
ruff check app tests && mypy app && lint-imports
```

PostgreSQL integration tests (Docker; uses port 55432 so it doesn't clash with Option A):
```bash
docker run -d --rm --name uss-pg-test -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=test -p 55432:5432 postgres:16-alpine
sleep 5
APP_TEST_DATABASE_URL=postgresql://test:test@localhost:55432/test pytest -m integration   # 4 passed
docker stop uss-pg-test
```

---

## 5. Stop and reset

```bash
docker compose -f deploy/docker-compose.yml down        # stop; keep data
docker compose -f deploy/docker-compose.yml down -v     # stop and delete all data (fresh demo next time)
```
For Option B, press `Ctrl+C` in the uvicorn terminal.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `port is already allocated` (5432 or 8000) | Another PostgreSQL or app is running. Stop it, or change the left-hand port in `deploy/docker-compose.yml`. |
| `failed to connect to the docker API` | Start Docker Desktop and wait for it to say *running*. |
| Smoke test exits with "API not reachable" | Start the stack (step 1) and wait for `/health/ready`. |
| `409 SLOT_UNAVAILABLE` in your own manual tests | That time is already taken. Use `/v1/availability`, or reset with `down -v`. |
| `422 LEAD_TIME_TOO_SHORT` / `BEYOND_BOOKING_HORIZON` | Pick a date at least 1 h ahead and within 90 days. |
| `422 VALIDATION_FAILED … timezone` | `desired_start_time` needs an offset such as `+05:30` or `Z`. |
| Schema changed but the DB is old | `down -v` and `up` again. The local migrate step skips an existing schema. |
