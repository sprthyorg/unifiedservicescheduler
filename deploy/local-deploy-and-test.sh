#!/usr/bin/env bash
# One command: deploy the full local stack, wait until it is ready, then test it automatically.
#
#   ./deploy/local-deploy-and-test.sh                 # deploy + smoke test (≈ 1 min)
#   ./deploy/local-deploy-and-test.sh --suite all     # + unit/API/contract, lint/types, PostgreSQL integration
#   ./deploy/local-deploy-and-test.sh --fresh --down  # wipe data first, tear down afterwards (CI-like)
#
# Options:
#   --suite smoke|all   what to run after deployment (default: smoke)
#   --fresh             delete the local database volume before deploying
#   --down              stop the stack (and delete its data) when finished
#   --no-build          reuse the existing image instead of rebuilding
# Exit code: 0 when every stage passed, 1 otherwise. A log is written to reports/.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/deploy/docker-compose.yml")
SERVICE="$ROOT/services/scheduler-service"
BASE="${BASE:-http://localhost:8000}"
SUITE=smoke; FRESH=0; DOWN=0; BUILD=(--build)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite) SUITE="$2"; shift 2 ;;
    --fresh) FRESH=1; shift ;;
    --down) DOWN=1; shift ;;
    --no-build) BUILD=(); shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$SUITE" == smoke || "$SUITE" == all ]] || { echo "--suite must be smoke or all" >&2; exit 2; }

mkdir -p "$ROOT/reports"
LOG="$ROOT/reports/local-test-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG") 2>&1

RESULTS=()
stage() { echo; echo "━━━ $1"; STAGE_START=$SECONDS; }
record() {  # record <name> <exit-code>
  local secs=$((SECONDS - STAGE_START))
  if [[ "$2" -eq 0 ]]; then RESULTS+=("✅ $1 (${secs}s)"); else RESULTS+=("❌ $1 (${secs}s)"); fi
  return "$2"
}
finish() {
  echo; echo "━━━ Summary"
  printf '  %s\n' "${RESULTS[@]}"
  if [[ $DOWN -eq 1 ]]; then "${COMPOSE[@]}" down -v >/dev/null 2>&1 && echo "  stack stopped, data deleted"; else echo "  stack still running at $BASE (docs: $BASE/docs)"; fi
  echo "  log: $LOG"
  [[ "${RESULTS[*]}" != *"❌"* ]] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
}
trap 'docker rm -f uss-pg-it >/dev/null 2>&1 || true' EXIT

# ── 1. Preflight ────────────────────────────────────────────────────────────────────────
stage "1. Preflight (Docker)"
if ! docker info >/dev/null 2>&1; then
  if [[ "$(uname)" == Darwin ]] && open -a Docker 2>/dev/null; then
    echo "Docker Desktop not running — starting it…"
    for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
  fi
fi
docker info >/dev/null 2>&1; record "Docker available" $? || { echo "Start Docker and retry."; finish; }

# ── 2. Deploy ───────────────────────────────────────────────────────────────────────────
stage "2. Deploy (PostgreSQL → migrations → API)"
[[ $FRESH -eq 1 ]] && "${COMPOSE[@]}" down -v >/dev/null 2>&1
"${COMPOSE[@]}" up -d ${BUILD[@]+"${BUILD[@]}"}; record "docker compose up" $? || finish

stage "3. Wait for readiness ($BASE/health/ready, up to 120 s)"
ready=1
for _ in $(seq 1 60); do curl -fs "$BASE/health/ready" >/dev/null && { ready=0; break; }; sleep 2; done
if [[ $ready -ne 0 ]]; then
  "${COMPOSE[@]}" ps; "${COMPOSE[@]}" logs --tail 40 migrate api
fi
record "API ready" $ready || finish

# ── 3. Tests against the deployed stack ─────────────────────────────────────────────────
stage "4. Smoke test against the deployed API"
BASE="$BASE" "$ROOT/deploy/local-smoke-test.sh"; record "Smoke test (16 checks)" $?

stage "5. Database integrity check (no overlapping CONFIRMED bookings — NFR-05)"
overlaps="$("${COMPOSE[@]}" exec -T postgres psql -U scheduler -tAc "
  SELECT count(*) FROM appointments a JOIN appointments b ON a.id < b.id
   AND a.status='CONFIRMED' AND b.status='CONFIRMED'
   AND (a.technician_id=b.technician_id OR a.service_bay_id=b.service_bay_id OR a.vehicle_id=b.vehicle_id)
   AND tstzrange(a.start_at,a.end_at) && tstzrange(b.start_at,b.end_at);" 2>&1)"
echo "overlapping pairs: $overlaps"
[[ "$overlaps" == 0 ]]; record "Integrity check" $?

# ── 4. Full suite (optional) ────────────────────────────────────────────────────────────
if [[ "$SUITE" == all ]]; then
  stage "6. Python test environment"
  if [[ ! -x "$SERVICE/.venv/bin/pytest" ]]; then
    python3 -m venv "$SERVICE/.venv" && "$SERVICE/.venv/bin/pip" install -q -r "$SERVICE/requirements-dev.txt"
  fi
  [[ -x "$SERVICE/.venv/bin/pytest" ]]; record "venv ready" $?

  stage "7. Lint, types, layering"
  (cd "$SERVICE" && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests \
     && .venv/bin/mypy app && .venv/bin/lint-imports); record "ruff + mypy + import contract" $?

  stage "8. Unit, use-case, API and contract tests"
  (cd "$SERVICE" && .venv/bin/pytest -p no:warnings); record "pytest" $?

  stage "9. PostgreSQL integration tests (throwaway database on :55432)"
  docker rm -f uss-pg-it >/dev/null 2>&1
  docker run -d --rm --name uss-pg-it -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \
    -p 55432:5432 postgres:16-alpine >/dev/null
  for _ in $(seq 1 30); do docker exec uss-pg-it pg_isready -U test -q 2>/dev/null && break; sleep 1; done; sleep 2
  (cd "$SERVICE" && APP_TEST_DATABASE_URL=postgresql://test:test@localhost:55432/test \
     .venv/bin/pytest -m integration -p no:warnings); record "pytest -m integration" $?
fi

finish
