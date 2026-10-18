#!/usr/bin/env bash
# End-to-end smoke test against a running scheduler API (default http://localhost:8000).
# Exercises FR-01..FR-08 with the demo data (dealership DLR-HYD-01, Asia/Kolkata).
#   ./deploy/local-smoke-test.sh                 # against docker compose / uvicorn on :8000
#   BASE=http://localhost:9000 ./deploy/local-smoke-test.sh
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
RUN="$(python3 -c "import uuid; print(uuid.uuid4().hex[:12])")"   # unique per run → fresh Idempotency-Keys
pass=0; fail=0

# Next Tuesday (dealership local date) — always ≥ 60 min ahead and within the 90-day horizon.
DAY="$(python3 -c 'import datetime as d; t=d.date.today(); print(t + d.timedelta(days=(1 - t.weekday()) % 7 or 7))')"
START="${DAY}T10:00:00+05:30"

check() {  # check <description> <expected> <actual>
  if [[ "$2" == "$3" ]]; then echo "  ✅ $1"; pass=$((pass + 1)); else echo "  ❌ $1 (expected $2, got $3)"; fail=$((fail + 1)); fi
}
json() { python3 -c "import sys,json; print(json.load(sys.stdin)$1)"; }
post() {  # post <path> <idempotency-key|-> <json>  → sets BODY and CODE
  local hdr=(-H 'Content-Type: application/json')
  [[ "$2" != "-" ]] && hdr+=(-H "Idempotency-Key: $2")
  local out; out="$(curl -s -w $'\n%{http_code}' -X POST "$BASE$1" "${hdr[@]}" -d "$3")"
  BODY="${out%$'\n'*}"; CODE="${out##*$'\n'}"
}
booking() {  # booking <customer> <vehicle> <service_type> <start>
  printf '{"customer_id":"%s","vehicle_id":"%s","dealership_id":"DLR-HYD-01","service_type_id":"%s","desired_start_time":"%s"}' "$@"
}

echo "Target: $BASE   Test date: $DAY (Tuesday)"
if ! curl -fs -o /dev/null "$BASE/health/live"; then
  echo "❌ API not reachable at $BASE — start it first (deploy/LOCAL-TESTING.md, step 1)." >&2
  exit 2
fi

echo "1. Health"
check "liveness 200" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health/live")"
check "readiness 200 (database reachable)" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health/ready")"

echo "2. Reference data + availability (FR-04)"
check "service types listed" True "$(curl -s "$BASE/v1/service-types" | json '.__len__() >= 4')"
SLOTS="$(curl -s "$BASE/v1/availability?dealership_id=DLR-HYD-01&service_type_id=SVC-EV-BATT&date=$DAY" | json '["slots"].__len__()')"
echo "     EV battery check slots available on $DAY before booking: $SLOTS"

echo "3. Book (FR-01, FR-02, FR-03)"
B1="$(booking CUS-1001 VEH-5001 SVC-EV-BATT "$START")"
post /v1/appointments "smoke-$RUN-1" "$B1"
check "booking returns 201" 201 "$CODE"
ID="$(echo "$BODY" | json '["id"]')"
echo "     appointment $ID → technician $(echo "$BODY" | json '["technician_id"]'), bay $(echo "$BODY" | json '["service_bay_id"]')"

echo "4. Idempotent retry (FR-08)"
post /v1/appointments "smoke-$RUN-1" "$B1"
check "same key + same body returns 200" 200 "$CODE"
check "…and the same appointment" "$ID" "$(echo "$BODY" | json '["id"]')"
post /v1/appointments - "$B1"
check "missing Idempotency-Key returns 400" 400 "$CODE"

echo "5. Conflict: only one EV technician, so a second EV job at the same time is refused (FR-02, FR-06)"
B2="$(booking CUS-1002 VEH-5002 SVC-EV-BATT "$START")"
post /v1/appointments "smoke-$RUN-2" "$B2"
check "second booking returns 409" 409 "$CODE"
check "code is SLOT_UNAVAILABLE" SLOT_UNAVAILABLE "$(echo "$BODY" | json '["code"]')"
check "3 alternative times offered" 3 "$(echo "$BODY" | json '["alternatives"].__len__()')"
echo "     alternatives: $(echo "$BODY" | python3 -c "import sys,json; print(', '.join(a['start_time'] for a in json.load(sys.stdin)['alternatives']))")"

echo "6. Validation (FR-09)"
post /v1/appointments "smoke-$RUN-3" "$(booking CUS-1001 VEH-5001 SVC-OIL "${DAY}T07:00:00+05:30")"
check "before opening hours returns 422 OUTSIDE_BUSINESS_HOURS" "422 OUTSIDE_BUSINESS_HOURS" "$CODE $(echo "$BODY" | json '["code"]')"
post /v1/appointments "smoke-$RUN-4" "$(booking CUS-1001 VEH-5002 SVC-OIL "${DAY}T14:00:00+05:30")"
check "someone else's vehicle returns 422" "422 VEHICLE_NOT_OWNED_BY_CUSTOMER" "$CODE $(echo "$BODY" | json '["code"]')"

echo "7. Read back (FR-05)"
check "GET by id returns CONFIRMED" CONFIRMED "$(curl -s "$BASE/v1/appointments/$ID" | json '["status"]')"

echo "8. Cancel frees the technician and bay (FR-07)"
post "/v1/appointments/$ID/cancel" - '{"customer_id":"CUS-1001","reason":"smoke test"}'
check "cancel returns 200 CANCELLED" "200 CANCELLED" "$CODE $(echo "$BODY" | json '["status"]')"
post /v1/appointments "smoke-$RUN-5" "$B2"
check "the previously refused booking now succeeds (201)" 201 "$CODE"
ID2="$(echo "$BODY" | json '["id"]')"
post "/v1/appointments/$ID2/cancel" - '{"customer_id":"CUS-1002","reason":"smoke cleanup"}'

echo "9. Metrics (NFR-10)"
check "business counter exported" True "$(curl -s "$BASE/metrics" | grep -q scheduler_appointments_confirmed_total && echo True || echo False)"

echo
echo "Result: $pass passed, $fail failed"
[[ $fail -eq 0 ]]
