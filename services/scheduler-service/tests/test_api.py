"""HTTP-level tests: status codes, headers and problem+json bodies (openapi_1.0.0.yaml)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import body

KEY = {"Idempotency-Key": "3f6c1a1e-0000-4000-8000-000000000001"}


def test_fr_01_fr_03_post_creates_appointment(client: TestClient) -> None:
    r = client.post("/v1/appointments", json=body(), headers=KEY)
    assert r.status_code == 201, r.text
    a = r.json()
    assert r.headers["Location"] == f"/v1/appointments/{a['id']}"
    assert a["status"] == "CONFIRMED"
    assert a["technician_id"] and a["service_bay_id"]
    assert a["start_time"].startswith("2026-10-20T04:30:00")  # stored and returned in UTC
    assert a["end_time"].startswith("2026-10-20T05:30:00")


def test_fr_08_replay_returns_200_and_same_body(client: TestClient) -> None:
    first = client.post("/v1/appointments", json=body(), headers=KEY)
    replay = client.post("/v1/appointments", json=body(), headers=KEY)
    assert replay.status_code == 200 and replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json() == first.json()
    reused = client.post("/v1/appointments", json=body(start="2026-10-20T11:00:00+05:30"), headers=KEY)
    assert reused.status_code == 409 and reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_fr_08_idempotency_key_is_required(client: TestClient) -> None:
    r = client.post("/v1/appointments", json=body())
    assert r.status_code == 400 and r.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_fr_02_fr_06_conflict_is_409_with_alternatives(client: TestClient) -> None:
    ev = body(service_type="SVC-EV-BATT")
    assert client.post("/v1/appointments", json=ev, headers=KEY).status_code == 201
    other = body(service_type="SVC-EV-BATT", customer="CUS-1002", vehicle="VEH-5002")
    r = client.post("/v1/appointments", json=other, headers={"Idempotency-Key": "another-key-123"})
    assert r.status_code == 409
    assert r.headers["content-type"] == "application/problem+json"
    p = r.json()
    assert p["code"] == "SLOT_UNAVAILABLE" and len(p["alternatives"]) == 3
    assert p["alternatives"][0]["start_time"] == "2026-10-20T08:15:00+05:30"


def test_fr_09_validation_errors_are_422(client: TestClient) -> None:
    naive = client.post("/v1/appointments", json=body(start="2026-10-20T10:00:00"), headers=KEY)
    assert naive.status_code == 422 and naive.json()["code"] == "VALIDATION_FAILED"
    extra = client.post("/v1/appointments", json=body() | {"technician_id": "TEC-001"}, headers=KEY)
    assert extra.status_code == 422  # clients cannot pick resources; the scheduler allocates them
    closed = client.post("/v1/appointments", json=body(start="2026-10-20T07:00:00+05:30"), headers=KEY)
    assert closed.status_code == 422 and closed.json()["code"] == "OUTSIDE_BUSINESS_HOURS"
    not_owner = client.post("/v1/appointments", json=body(vehicle="VEH-5002"), headers=KEY)
    assert not_owner.status_code == 422 and not_owner.json()["code"] == "VEHICLE_NOT_OWNED_BY_CUSTOMER"


def test_fr_05_get_and_list(client: TestClient) -> None:
    a = client.post("/v1/appointments", json=body(), headers=KEY).json()
    assert client.get(f"/v1/appointments/{a['id']}").json() == a
    listed = client.get("/v1/appointments", params={"customer_id": "CUS-1001"}).json()
    assert [x["id"] for x in listed["items"]] == [a["id"]]
    missing = client.get("/v1/appointments/00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 404 and missing.json()["code"] == "APPOINTMENT_NOT_FOUND"
    assert client.get("/v1/appointments/not-a-uuid").status_code == 422


def test_fr_07_cancel(client: TestClient) -> None:
    a = client.post("/v1/appointments", json=body(), headers=KEY).json()
    r = client.post(f"/v1/appointments/{a['id']}/cancel", json={"customer_id": "CUS-1001", "reason": "sick"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED" and r.json()["cancellation_reason"] == "sick"
    wrong = client.post(f"/v1/appointments/{a['id']}/cancel", json={"customer_id": "CUS-1002"})
    assert wrong.status_code == 404


def test_fr_04_availability(client: TestClient) -> None:
    r = client.get(
        "/v1/availability", params={"dealership_id": "DLR-HYD-01", "service_type_id": "SVC-ALIGN", "date": "2026-10-20"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["timezone"] == "Asia/Kolkata" and data["duration_minutes"] == 45
    assert data["slots"][0] == {
        "start_time": "2026-10-20T09:00:00+05:30",
        "end_time": "2026-10-20T09:45:00+05:30",
        "capacity": 1,
    }
    bad = client.get(
        "/v1/availability", params={"dealership_id": "X", "service_type_id": "SVC-OIL", "date": "2026-10-20"}
    )
    assert bad.status_code == 422 and bad.json()["code"] == "UNKNOWN_DEALERSHIP"


def test_reference_endpoints(client: TestClient) -> None:
    assert [d["id"] for d in client.get("/v1/dealerships").json()] == ["DLR-HYD-01"]
    assert {s["id"] for s in client.get("/v1/service-types").json()} >= {"SVC-OIL", "SVC-EV-BATT"}


def test_nfr_10_health_metrics_and_request_id(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 200
    r = client.post("/v1/appointments", json=body(), headers=KEY | {"X-Request-ID": "req-123"})
    assert r.headers["X-Request-ID"] == "req-123"
    client.post(
        "/v1/appointments", json=body(start="2026-10-20T07:00:00+05:30"), headers={"Idempotency-Key": "k-2-abcdef"}
    )
    m = client.get("/metrics").text
    assert (
        'http_requests_total{service="scheduler-service",method="POST",route="/v1/appointments",status="201"} 1.0' in m
    )
    assert 'scheduler_appointments_confirmed_total{service="scheduler-service",dealership_id="DLR-HYD-01"} 1.0' in m
    assert 'scheduler_booking_rejections_total{service="scheduler-service",code="OUTSIDE_BUSINESS_HOURS"} 1.0' in m
