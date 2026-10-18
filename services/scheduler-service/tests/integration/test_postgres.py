"""Integration tests against a real PostgreSQL 16 (NFR-05). Run with:

    APP_TEST_DATABASE_URL=postgresql://test:test@localhost:5432/test pytest -m integration

The database must be empty; migrations/V001 and V002 are applied by the fixture.
"""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from app.domain import errors as e
from app.services.scheduling_service import SchedulingService
from tests.conftest import FakeClock, cmd, ist

pytestmark = pytest.mark.integration

DSN = os.getenv("APP_TEST_DATABASE_URL")
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


@pytest.fixture(scope="module")
def pg() -> Iterator[object]:
    if not DSN:
        pytest.skip("APP_TEST_DATABASE_URL not set")
    import psycopg

    from app.repositories.postgres import PostgresDatabase

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        for f in sorted(MIGRATIONS.glob("V*.sql")):
            conn.execute(f.read_text())  # type: ignore[arg-type]
        for i in range(10):  # racers for the concurrency test
            conn.execute("INSERT INTO customers VALUES (%s, 'Racer')", (f"CUS-R{i}",))
            conn.execute(
                "INSERT INTO vehicles VALUES (%s, %s, %s, 'Make', 'Model', 2024)",
                (f"VEH-R{i}", f"CUS-R{i}", f"VINR{i:013d}"),
            )
    db = PostgresDatabase(DSN, max_size=12)
    yield db
    db.close()


@pytest.fixture
def svc(pg: object) -> SchedulingService:
    from app.repositories.postgres import PostgresDatabase, PostgresUnitOfWork

    assert isinstance(pg, PostgresDatabase)
    with pg.pool.connection() as conn:
        conn.execute("TRUNCATE appointments, outbox")
    return SchedulingService(lambda: PostgresUnitOfWork(pg), clock=FakeClock())


def test_fr_03_record_round_trips_through_postgres(svc: SchedulingService) -> None:
    a = svc.book_appointment(cmd(ist(20, 10), "SVC-PERIODIC"), "pg-key-001").appointment
    assert svc.get_appointment(a.id) == a
    assert svc.list_for_customer("CUS-1001")[0].id == a.id
    assert svc.book_appointment(cmd(ist(20, 10), "SVC-PERIODIC"), "pg-key-001").created is False


def test_fr_02_concurrent_requests_never_double_book(svc: SchedulingService) -> None:
    outcomes: list[str] = []
    barrier = threading.Barrier(10)

    def attempt(i: int) -> None:
        barrier.wait()
        try:
            svc.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT", f"CUS-R{i}", f"VEH-R{i}"), f"pg-race-{i}")
            outcomes.append("ok")
        except e.SlotUnavailable:
            outcomes.append("conflict")

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ["conflict"] * 9 + ["ok"]


def test_nfr_05_exclusion_constraint_blocks_overlap_even_if_app_logic_is_bypassed(
    svc: SchedulingService, pg: object
) -> None:
    import psycopg

    from app.repositories.postgres import PostgresDatabase

    assert isinstance(pg, PostgresDatabase)
    a = svc.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT"), "pg-key-002").appointment
    with pg.pool.connection() as conn, pytest.raises(psycopg.errors.ExclusionViolation):
        conn.execute(
            "INSERT INTO appointments (id, reference, customer_id, vehicle_id, dealership_id, service_type_id, "
            "technician_id, service_bay_id, start_at, end_at, status, idempotency_key, request_hash) "
            "VALUES (%s, 'APT-MANUAL1', 'CUS-1002', 'VEH-5002', 'DLR-HYD-01', 'SVC-EV-BATT', %s, 'BAY-01', "
            "%s, %s, 'CONFIRMED', 'manual', repeat('0', 64))",
            (uuid.uuid4(), a.technician_id, a.start + timedelta(minutes=30), a.end + timedelta(minutes=30)),
        )


def test_fr_07_cancel_frees_the_slot_in_postgres(svc: SchedulingService) -> None:
    a = svc.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT"), "pg-key-003").appointment
    svc.cancel_appointment(a.id, customer_id="CUS-1001")
    again = svc.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT", "CUS-1002", "VEH-5002"), "pg-key-004")
    assert again.appointment.technician_id == a.technician_id
