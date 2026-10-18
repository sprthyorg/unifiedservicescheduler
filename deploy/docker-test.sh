#!/usr/bin/env bash
# Build and run every test suite inside Docker, then remove all test containers and data.
# Needs only Docker — no local Python. Exit code 0 = all suites passed.
#   ./deploy/docker-test.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/deploy/docker-compose.test.yml")

if ! docker info >/dev/null 2>&1 && [[ "$(uname)" == Darwin ]] && open -a Docker 2>/dev/null; then
  echo "Starting Docker Desktop…"; for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
fi
docker info >/dev/null 2>&1 || { echo "Docker is not running." >&2; exit 2; }

mkdir -p "$ROOT/reports"
cleanup() { "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1; }
trap cleanup EXIT
cleanup                                   # leftovers from an interrupted run

echo "Building images…"
"${COMPOSE[@]}" build --quiet || exit 1
echo "Starting postgres → migrate → api, test-db; then running the test container…"
"${COMPOSE[@]}" run --rm tests
status=$?
if [[ $status -ne 0 ]]; then
  echo; echo "Deployed-stack logs (last 30 lines):"; "${COMPOSE[@]}" logs --tail 30 migrate api
fi
exit $status
