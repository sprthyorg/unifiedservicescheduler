#!/usr/bin/env bash
# Runs inside the test-runner container (deploy/docker-compose.test.yml). Every suite, one summary.
#   stages: static checks → unit/API/contract → PostgreSQL integration → smoke vs. deployed API → DB integrity
# Env: BASE (deployed API), APP_TEST_DATABASE_URL (empty throwaway DB), APP_DEPLOYED_DATABASE_URL (deployed DB)
set -uo pipefail
cd /repo/services/scheduler-service
REPORTS=/repo/reports; mkdir -p "$REPORTS"
RESULTS=()
run() {  # run <name> <command...>
  local name="$1"; shift; local t=$SECONDS
  echo; echo "━━━ $name"
  if "$@"; then RESULTS+=("✅ $name ($((SECONDS - t))s)"); else RESULTS+=("❌ $name ($((SECONDS - t))s)"); fi
}

integrity() {
  python - <<'PY'
import os, psycopg
sql = """SELECT count(*) FROM appointments a JOIN appointments b ON a.id < b.id
 AND a.status='CONFIRMED' AND b.status='CONFIRMED'
 AND (a.technician_id=b.technician_id OR a.service_bay_id=b.service_bay_id OR a.vehicle_id=b.vehicle_id)
 AND tstzrange(a.start_at,a.end_at) && tstzrange(b.start_at,b.end_at)"""
with psycopg.connect(os.environ["APP_DEPLOYED_DATABASE_URL"]) as c:
    n = c.execute(sql).fetchone()[0]
print(f"overlapping CONFIRMED pairs: {n}")
raise SystemExit(0 if n == 0 else 1)
PY
}

run "Lint + format (ruff)"            bash -c "ruff check app tests && ruff format --check app tests"
run "Types (mypy --strict)"           mypy app
run "Layering (import-linter)"        lint-imports
run "Unit, API, contract tests"       pytest -p no:warnings --junitxml="$REPORTS/junit-unit.xml"
run "PostgreSQL integration tests"    pytest -m integration -p no:warnings --junitxml="$REPORTS/junit-integration.xml"
run "Smoke test vs deployed API"      bash /repo/deploy/local-smoke-test.sh
run "DB integrity (NFR-05)"           integrity

echo; echo "━━━ Summary"; printf '  %s\n' "${RESULTS[@]}"
echo "  JUnit reports: reports/junit-unit.xml, reports/junit-integration.xml"
if [[ "${RESULTS[*]}" == *"❌"* ]]; then echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: PASS"
