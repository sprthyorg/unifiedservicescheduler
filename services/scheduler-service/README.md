# scheduler-service 1.0.0

Books vehicle service appointments by allocating a **qualified technician** and a **compatible
service bay** that are both free for the **entire** service duration.

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                                   # 53 unit, API and contract tests
APP_SEED_DEMO_DATA=true uvicorn app.main:app --reload    # http://localhost:8000/docs (in-memory)
```

With PostgreSQL, use `docker compose -f ../../deploy/docker-compose.yml up --build`. Integration tests:

```bash
docker run -d --rm --name pg -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test -p 5432:5432 postgres:16-alpine
APP_TEST_DATABASE_URL=postgresql://test:test@localhost:5432/test pytest -m integration
```

## Try it (demo data, dealership DLR-HYD-01, Asia/Kolkata)

```bash
curl -s "localhost:8000/v1/availability?dealership_id=DLR-HYD-01&service_type_id=SVC-EV-BATT&date=2026-10-20"
curl -s -X POST localhost:8000/v1/appointments -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"customer_id":"CUS-1001","vehicle_id":"VEH-5001","dealership_id":"DLR-HYD-01",
       "service_type_id":"SVC-EV-BATT","desired_start_time":"2026-10-20T10:00:00+05:30"}'
```

## Layout

| Path | Role |
|---|---|
| `app/domain/` | Entities, `allocation.py` (the two-resource rule), events, ports, errors. Framework-free. |
| `app/services/scheduling_service.py` | Use cases: book, availability, get/list, cancel |
| `app/repositories/` | `memory.py` (dev and tests), `postgres.py` (advisory lock, exclusion-constraint mapping) |
| `app/api/` | FastAPI routes, schemas, RFC 9457 errors |
| `migrations/` | `V001` schema, `V002` demo seed (non-production) |
| `tests/` | `test_fr_xx_*` per requirement; `contract/`; `integration/` |

## Configuration (`APP_*`)

| Variable | Default | Meaning |
|---|---|---|
| `APP_DATABASE_URL` | unset → in-memory | PostgreSQL DSN |
| `APP_SEED_DEMO_DATA` | false | Seed demo data (in-memory only) |
| `APP_SLOT_GRANULARITY_MINUTES` | 15 | Start-time grid (A-05) |
| `APP_MIN_LEAD_TIME_MINUTES` | 60 | Minimum notice (A-06) |
| `APP_BOOKING_HORIZON_DAYS` | 90 | How far ahead (A-07) |
| `APP_ALTERNATIVES_COUNT` / `APP_ALTERNATIVES_SEARCH_DAYS` | 3 / 7 | Alternatives on conflict (FR-06) |
| `APP_DB_POOL_MAX_SIZE` | 10 | Connections per pod |
| `APP_LOG_LEVEL` | INFO | |
