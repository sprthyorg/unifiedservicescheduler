"""In-memory adapter for local development and tests.

A unit of work holds the database-wide lock for its whole lifetime and stages writes until commit(),
which gives the same serialisable outcome the Postgres adapter gets from its advisory lock and
exclusion constraints.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Sequence
from datetime import time
from types import TracebackType
from typing import Self

from app.domain.errors import ConcurrentModification, IdempotencyKeyReused, SlotUnavailable
from app.domain.events import DomainEvent
from app.domain.models import (
    Appointment,
    Customer,
    DailyWindow,
    Dealership,
    ServiceBay,
    ServiceType,
    Technician,
    TimeRange,
    Vehicle,
)


class InMemoryDatabase:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.dealerships: dict[str, Dealership] = {}
        self.service_types: dict[str, ServiceType] = {}
        self.customers: dict[str, Customer] = {}
        self.vehicles: dict[str, Vehicle] = {}
        self.technicians: dict[str, Technician] = {}
        self.bays: dict[str, ServiceBay] = {}
        self.appointments: dict[uuid.UUID, Appointment] = {}
        self.outbox: list[DomainEvent] = []

    def ping(self) -> bool:
        return True


class _Reference:
    def __init__(self, db: InMemoryDatabase) -> None:
        self._db = db

    def dealership(self, dealership_id: str) -> Dealership | None:
        return self._db.dealerships.get(dealership_id)

    def list_dealerships(self) -> Sequence[Dealership]:
        return sorted(self._db.dealerships.values(), key=lambda d: d.id)

    def service_type(self, service_type_id: str) -> ServiceType | None:
        return self._db.service_types.get(service_type_id)

    def list_service_types(self) -> Sequence[ServiceType]:
        return sorted((s for s in self._db.service_types.values() if s.active), key=lambda s: s.id)

    def customer(self, customer_id: str) -> Customer | None:
        return self._db.customers.get(customer_id)

    def vehicle(self, vehicle_id: str) -> Vehicle | None:
        return self._db.vehicles.get(vehicle_id)

    def technicians(self, dealership_id: str) -> Sequence[Technician]:
        return [t for t in self._db.technicians.values() if t.dealership_id == dealership_id]

    def bays(self, dealership_id: str) -> Sequence[ServiceBay]:
        return [b for b in self._db.bays.values() if b.dealership_id == dealership_id]


class _Appointments:
    def __init__(self, db: InMemoryDatabase) -> None:
        self._db = db
        self.staged: dict[uuid.UUID, Appointment] = {}

    def _all(self) -> list[Appointment]:
        return list({**self._db.appointments, **self.staged}.values())

    def get(self, appointment_id: uuid.UUID) -> Appointment | None:
        return self.staged.get(appointment_id) or self._db.appointments.get(appointment_id)

    def by_idempotency_key(self, customer_id: str, key: str) -> Appointment | None:
        return next((a for a in self._all() if a.customer_id == customer_id and a.idempotency_key == key), None)

    def list_for_customer(self, customer_id: str, limit: int) -> Sequence[Appointment]:
        mine = [a for a in self._all() if a.customer_id == customer_id]
        return sorted(mine, key=lambda a: a.start, reverse=True)[:limit]

    def confirmed_in_range(self, dealership_id: str, window: TimeRange) -> Sequence[Appointment]:
        return [
            a for a in self._all() if a.dealership_id == dealership_id and a.is_active and a.period.overlaps(window)
        ]

    def confirmed_for_vehicle(self, vehicle_id: str, window: TimeRange) -> Sequence[Appointment]:
        return [a for a in self._all() if a.vehicle_id == vehicle_id and a.is_active and a.period.overlaps(window)]

    def add(self, appointment: Appointment) -> None:
        # Same invariants the Postgres exclusion / unique constraints enforce (V001__init_schema.sql).
        for other in self._all():
            if other.customer_id == appointment.customer_id and other.idempotency_key == appointment.idempotency_key:
                raise IdempotencyKeyReused("duplicate idempotency key")
            if (
                other.is_active
                and other.period.overlaps(appointment.period)
                and (
                    other.technician_id == appointment.technician_id
                    or other.service_bay_id == appointment.service_bay_id
                )
            ):
                raise SlotUnavailable("resource was booked concurrently")
        self.staged[appointment.id] = appointment

    def update(self, appointment: Appointment, *, expected_version: int) -> None:
        current = self.get(appointment.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModification("appointment was modified concurrently")
        self.staged[appointment.id] = appointment


class _Outbox:
    def __init__(self) -> None:
        self.staged: list[DomainEvent] = []

    def add(self, event: DomainEvent) -> None:
        self.staged.append(event)


class InMemoryUnitOfWork:
    def __init__(self, db: InMemoryDatabase) -> None:
        self._db = db
        self.reference = _Reference(db)
        self.appointments = _Appointments(db)
        self.outbox = _Outbox()

    def __enter__(self) -> Self:
        self._db.lock.acquire()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.appointments.staged.clear()  # anything not committed is discarded
        self.outbox.staged.clear()
        self._db.lock.release()

    def lock_dealership(self, dealership_id: str) -> None:
        return None  # the whole in-memory database is already locked for this unit of work

    def commit(self) -> None:
        self._db.appointments.update(self.appointments.staged)
        self._db.outbox.extend(self.outbox.staged)
        self.appointments.staged.clear()
        self.outbox.staged.clear()


# ------------------------------------------------------------------------------------------------
# Demo data — mirrors migrations/V002__seed_demo_reference_data.sql
# ------------------------------------------------------------------------------------------------
def _weekdays(opens: str, closes: str, days: range = range(1, 7)) -> dict[int, DailyWindow]:
    return {d: DailyWindow(time.fromisoformat(opens), time.fromisoformat(closes)) for d in days}


def seed_demo_data(db: InMemoryDatabase) -> None:
    db.dealerships["DLR-HYD-01"] = Dealership(
        "DLR-HYD-01", "Hyderabad Central Motors", "Asia/Kolkata", _weekdays("08:00", "18:00")
    )
    for st in (
        ServiceType("SVC-OIL", "Oil & filter change", 60, "GENERAL", "LIFT"),
        ServiceType("SVC-PERIODIC", "Periodic maintenance service", 180, "GENERAL", "LIFT"),
        ServiceType("SVC-ALIGN", "Wheel alignment", 45, "ALIGNMENT", "ALIGNMENT_RIG"),
        ServiceType("SVC-EV-BATT", "EV battery health check", 90, "EV_HIGH_VOLTAGE", "EV_SAFE"),
    ):
        db.service_types[st.id] = st
    for b in (
        ServiceBay("BAY-01", "DLR-HYD-01", "Bay 1", frozenset({"LIFT"})),
        ServiceBay("BAY-02", "DLR-HYD-01", "Bay 2", frozenset({"LIFT"})),
        ServiceBay("BAY-03", "DLR-HYD-01", "Bay 3 (alignment)", frozenset({"LIFT", "ALIGNMENT_RIG"})),
        ServiceBay("BAY-04", "DLR-HYD-01", "Bay 4 (EV)", frozenset({"LIFT", "EV_SAFE"})),
    ):
        db.bays[b.id] = b
    for t in (
        Technician("TEC-001", "DLR-HYD-01", "Ravi Kumar", frozenset({"GENERAL"}), _weekdays("08:00", "17:00")),
        Technician(
            "TEC-002", "DLR-HYD-01", "Anita Rao", frozenset({"GENERAL", "ALIGNMENT"}), _weekdays("09:00", "18:00")
        ),
        Technician(
            "TEC-003",
            "DLR-HYD-01",
            "Imran Shaikh",
            frozenset({"GENERAL", "EV_HIGH_VOLTAGE"}),
            _weekdays("08:00", "17:00"),
        ),
    ):
        db.technicians[t.id] = t
    db.customers["CUS-1001"] = Customer("CUS-1001", "Demo Customer A")
    db.customers["CUS-1002"] = Customer("CUS-1002", "Demo Customer B")
    db.vehicles["VEH-5001"] = Vehicle("VEH-5001", "CUS-1001", "MA3EYD32S00123456", "Maruti", "Swift", 2023)
    db.vehicles["VEH-5002"] = Vehicle("VEH-5002", "CUS-1002", "MAT625402P0K12345", "Tata", "Nexon EV", 2024)
