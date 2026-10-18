"""PostgreSQL adapter (psycopg 3 + connection pool).

Double-booking is prevented twice over (ADR-002):
  1. `pg_advisory_xact_lock` serialises booking decisions per dealership, so the read-check-insert
     sequence in SchedulingService.book_appointment never interleaves for the same resources;
  2. GiST exclusion constraints on (technician_id, period) and (service_bay_id, period) reject any
     overlapping CONFIRMED rows even if application logic is bypassed or buggy.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import time
from types import TracebackType
from typing import Any, Self, cast

import psycopg
from psycopg import errors as pg_errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from app.domain.errors import ConcurrentModification, IdempotencyKeyReused, SlotUnavailable, VehicleAlreadyBooked
from app.domain.events import DomainEvent
from app.domain.models import (
    Appointment,
    AppointmentStatus,
    Customer,
    DailyWindow,
    Dealership,
    ServiceBay,
    ServiceType,
    Technician,
    TimeRange,
    Vehicle,
)

_log = logging.getLogger("repositories.postgres")

_APPT_COLS = (
    "id, reference, customer_id, vehicle_id, dealership_id, service_type_id, technician_id, service_bay_id, "
    "start_at, end_at, status, idempotency_key, request_hash, created_at, updated_at, version, notes, "
    "cancelled_at, cancellation_reason"
)


class PostgresDatabase:
    def __init__(self, dsn: str, max_size: int = 10) -> None:
        self.pool = ConnectionPool(dsn, min_size=1, max_size=max_size, kwargs={"row_factory": dict_row}, open=True)

    def ping(self) -> bool:
        try:
            with self.pool.connection(timeout=2) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def close(self) -> None:
        self.pool.close()


def _schedule(rows: Sequence[dict[str, Any]], start: str, end: str) -> dict[int, DailyWindow]:
    return {int(r["weekday"]): DailyWindow(r[start], r[end]) for r in rows}


def _to_appointment(r: dict[str, Any]) -> Appointment:
    return Appointment(
        id=r["id"],
        reference=r["reference"],
        customer_id=r["customer_id"],
        vehicle_id=r["vehicle_id"],
        dealership_id=r["dealership_id"],
        service_type_id=r["service_type_id"],
        technician_id=r["technician_id"],
        service_bay_id=r["service_bay_id"],
        start=r["start_at"],
        end=r["end_at"],
        status=AppointmentStatus(r["status"]),
        idempotency_key=r["idempotency_key"],
        request_hash=r["request_hash"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        version=r["version"],
        notes=r["notes"],
        cancelled_at=r["cancelled_at"],
        cancellation_reason=r["cancellation_reason"],
    )


class _Reference:
    def __init__(self, conn: psycopg.Connection[dict[str, Any]]) -> None:
        self._c = conn

    def _dealership(self, row: dict[str, Any]) -> Dealership:
        hours = self._c.execute(
            "SELECT weekday, opens_at, closes_at FROM dealership_hours WHERE dealership_id = %s", (row["id"],)
        ).fetchall()
        return Dealership(row["id"], row["name"], row["timezone"], _schedule(hours, "opens_at", "closes_at"))

    def dealership(self, dealership_id: str) -> Dealership | None:
        row = self._c.execute(
            "SELECT id, name, timezone FROM dealerships WHERE id = %s AND active", (dealership_id,)
        ).fetchone()
        return self._dealership(row) if row else None

    def list_dealerships(self) -> Sequence[Dealership]:
        rows = self._c.execute("SELECT id, name, timezone FROM dealerships WHERE active ORDER BY id").fetchall()
        return [self._dealership(r) for r in rows]

    @staticmethod
    def _service_type(r: dict[str, Any]) -> ServiceType:
        return ServiceType(
            r["id"], r["name"], r["duration_minutes"], r["required_skill"], r["required_bay_capability"], r["active"]
        )

    def service_type(self, service_type_id: str) -> ServiceType | None:
        r = self._c.execute("SELECT * FROM service_types WHERE id = %s", (service_type_id,)).fetchone()
        return self._service_type(r) if r else None

    def list_service_types(self) -> Sequence[ServiceType]:
        rows = self._c.execute("SELECT * FROM service_types WHERE active ORDER BY id").fetchall()
        return [self._service_type(r) for r in rows]

    def customer(self, customer_id: str) -> Customer | None:
        r = self._c.execute("SELECT id, display_name FROM customers WHERE id = %s", (customer_id,)).fetchone()
        return Customer(r["id"], r["display_name"]) if r else None

    def vehicle(self, vehicle_id: str) -> Vehicle | None:
        r = self._c.execute(
            "SELECT id, customer_id, vin, make, model, model_year FROM vehicles WHERE id = %s", (vehicle_id,)
        ).fetchone()
        return Vehicle(r["id"], r["customer_id"], r["vin"], r["make"], r["model"], r["model_year"]) if r else None

    def technicians(self, dealership_id: str) -> Sequence[Technician]:
        techs = self._c.execute(
            "SELECT id, dealership_id, name, skills, active FROM technicians WHERE dealership_id = %s ORDER BY id",
            (dealership_id,),
        ).fetchall()
        shifts = self._c.execute(
            "SELECT s.technician_id, s.weekday, s.starts_at, s.ends_at FROM technician_shifts s "
            "JOIN technicians t ON t.id = s.technician_id WHERE t.dealership_id = %s",
            (dealership_id,),
        ).fetchall()
        by_tech: dict[str, dict[int, DailyWindow]] = {}
        for s in shifts:
            start: time = s["starts_at"]
            by_tech.setdefault(s["technician_id"], {})[int(s["weekday"])] = DailyWindow(start, s["ends_at"])
        return [
            Technician(
                t["id"], t["dealership_id"], t["name"], frozenset(t["skills"]), by_tech.get(t["id"], {}), t["active"]
            )
            for t in techs
        ]

    def bays(self, dealership_id: str) -> Sequence[ServiceBay]:
        rows = self._c.execute(
            "SELECT id, dealership_id, name, capabilities, active FROM service_bays "
            "WHERE dealership_id = %s ORDER BY id",
            (dealership_id,),
        ).fetchall()
        return [
            ServiceBay(r["id"], r["dealership_id"], r["name"], frozenset(r["capabilities"]), r["active"]) for r in rows
        ]


class _Appointments:
    def __init__(self, conn: psycopg.Connection[dict[str, Any]]) -> None:
        self._c = conn

    def _one(self, sql: str, params: tuple[Any, ...]) -> Appointment | None:
        r = self._c.execute(sql, params).fetchone()
        return _to_appointment(r) if r else None

    def _many(self, sql: str, params: tuple[Any, ...]) -> list[Appointment]:
        return [_to_appointment(r) for r in self._c.execute(sql, params).fetchall()]

    def get(self, appointment_id: uuid.UUID) -> Appointment | None:
        return self._one(f"SELECT {_APPT_COLS} FROM appointments WHERE id = %s", (appointment_id,))

    def by_idempotency_key(self, customer_id: str, key: str) -> Appointment | None:
        return self._one(
            f"SELECT {_APPT_COLS} FROM appointments WHERE customer_id = %s AND idempotency_key = %s",
            (customer_id, key),
        )

    def list_for_customer(self, customer_id: str, limit: int) -> Sequence[Appointment]:
        return self._many(
            f"SELECT {_APPT_COLS} FROM appointments WHERE customer_id = %s ORDER BY start_at DESC LIMIT %s",
            (customer_id, limit),
        )

    def confirmed_in_range(self, dealership_id: str, window: TimeRange) -> Sequence[Appointment]:
        return self._many(
            f"SELECT {_APPT_COLS} FROM appointments WHERE dealership_id = %s AND status = 'CONFIRMED' "
            "AND start_at < %s AND end_at > %s",
            (dealership_id, window.end, window.start),
        )

    def confirmed_for_vehicle(self, vehicle_id: str, window: TimeRange) -> Sequence[Appointment]:
        return self._many(
            f"SELECT {_APPT_COLS} FROM appointments WHERE vehicle_id = %s AND status = 'CONFIRMED' "
            "AND start_at < %s AND end_at > %s",
            (vehicle_id, window.end, window.start),
        )

    def add(self, a: Appointment) -> None:
        try:
            with self._c.transaction():  # savepoint: a constraint error must not poison the outer tx
                self._c.execute(
                    f"INSERT INTO appointments ({_APPT_COLS}) VALUES "
                    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        a.id,
                        a.reference,
                        a.customer_id,
                        a.vehicle_id,
                        a.dealership_id,
                        a.service_type_id,
                        a.technician_id,
                        a.service_bay_id,
                        a.start,
                        a.end,
                        a.status.value,
                        a.idempotency_key,
                        a.request_hash,
                        a.created_at,
                        a.updated_at,
                        a.version,
                        a.notes,
                        a.cancelled_at,
                        a.cancellation_reason,
                    ),
                )
        except pg_errors.ExclusionViolation as exc:
            constraint = getattr(exc.diag, "constraint_name", "") or ""
            # Should be unreachable while the advisory lock is held: alert on it (runbook RB-04).
            _log.warning("exclusion constraint backstop triggered", extra={"code": "EXCLUSION_BACKSTOP"})
            if "vehicle" in constraint:
                raise VehicleAlreadyBooked("vehicle already has an overlapping appointment") from exc
            raise SlotUnavailable("resource was booked concurrently") from exc
        except pg_errors.UniqueViolation as exc:
            raise IdempotencyKeyReused("duplicate idempotency key") from exc

    def update(self, a: Appointment, *, expected_version: int) -> None:
        cur = self._c.execute(
            "UPDATE appointments SET status = %s, version = %s, updated_at = %s, cancelled_at = %s, "
            "cancellation_reason = %s WHERE id = %s AND version = %s",
            (a.status.value, a.version, a.updated_at, a.cancelled_at, a.cancellation_reason, a.id, expected_version),
        )
        if cur.rowcount != 1:
            raise ConcurrentModification("appointment was modified concurrently")


class _Outbox:
    def __init__(self, conn: psycopg.Connection[dict[str, Any]]) -> None:
        self._c = conn

    def add(self, event: DomainEvent) -> None:
        self._c.execute(
            "INSERT INTO outbox (id, aggregate_id, event_type, schema_version, payload, occurred_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (event.id, event.aggregate_id, event.type, event.schema_version, Jsonb(event.payload), event.occurred_at),
        )


class PostgresUnitOfWork:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    def __enter__(self) -> Self:
        self._ctx = self._db.pool.connection()
        self._conn = cast("psycopg.Connection[dict[str, Any]]", self._ctx.__enter__())
        self._committed = False
        self.reference = _Reference(self._conn)
        self.appointments = _Appointments(self._conn)
        self.outbox = _Outbox(self._conn)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        if not self._committed:
            self._conn.rollback()
        self._ctx.__exit__(exc_type, exc, tb)

    def lock_dealership(self, dealership_id: str) -> None:
        self._conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"dealership:{dealership_id}",))

    def commit(self) -> None:
        self._conn.commit()
        self._committed = True
