"""Unit tests for the pure allocation rules (FR-02, ADR-003)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from app.domain import allocation
from app.domain.models import Appointment, AppointmentStatus, ServiceBay, TimeRange
from app.repositories.memory import InMemoryDatabase
from tests.conftest import DEALER, ist


def _appt(
    tech: str, bay: str, start_h: int, minutes: int, status: AppointmentStatus = AppointmentStatus.CONFIRMED
) -> Appointment:
    start = ist(20, start_h)
    return Appointment(
        id=uuid.uuid4(),
        reference="APT-TEST",
        customer_id="C",
        vehicle_id="V",
        dealership_id=DEALER,
        service_type_id="SVC-OIL",
        technician_id=tech,
        service_bay_id=bay,
        start=start,
        end=start + timedelta(minutes=minutes),
        status=status,
        idempotency_key=uuid.uuid4().hex,
        request_hash="h",
        created_at=start,
        updated_at=start,
    )


def _ctx(db: InMemoryDatabase, service_type: str = "SVC-OIL"):  # type: ignore[no-untyped-def]
    d = db.dealerships[DEALER]
    st = db.service_types[service_type]
    techs = [t for t in db.technicians.values()]
    bays = [b for b in db.bays.values()]
    return d, st, techs, bays


def test_time_range_is_half_open() -> None:
    a = TimeRange(ist(20, 10), ist(20, 11))
    assert not a.overlaps(TimeRange(ist(20, 11), ist(20, 12)))  # back-to-back is fine
    assert a.overlaps(TimeRange(ist(20, 10, 59), ist(20, 12)))
    with pytest.raises(ValueError):
        TimeRange(ist(20, 11), ist(20, 10))


def test_fr_02_within_opening_hours_checks_whole_duration(db: InMemoryDatabase) -> None:
    d = db.dealerships[DEALER]
    assert allocation.within_opening_hours(d, TimeRange(ist(20, 17), ist(20, 18)))
    assert not allocation.within_opening_hours(d, TimeRange(ist(20, 17), ist(20, 18, 15)))
    assert not allocation.within_opening_hours(d, TimeRange(ist(25, 10), ist(25, 11)))  # Sunday closed


def test_fr_02_skill_filter(db: InMemoryDatabase) -> None:
    d, st, techs, _ = _ctx(db, "SVC-EV-BATT")
    free = allocation.free_technicians(d, st, techs, [], TimeRange(ist(20, 10), ist(20, 11, 30)))
    assert [t.id for t in free] == ["TEC-003"]


def test_fr_02_bay_capability_filter(db: InMemoryDatabase) -> None:
    d, st, _, bays = _ctx(db, "SVC-ALIGN")
    free = allocation.free_bays(d, st, bays, [], TimeRange(ist(20, 10), ist(20, 10, 45)))
    assert [b.id for b in free] == ["BAY-03"]


def test_fr_02_shift_must_cover_duration(db: InMemoryDatabase) -> None:
    d, st, techs, _ = _ctx(db)
    early = TimeRange(ist(20, 8), ist(20, 9))  # TEC-002 starts 09:00
    assert "TEC-002" not in {t.id for t in allocation.free_technicians(d, st, techs, [], early)}


def test_fr_02_busy_resources_excluded_and_cancelled_ignored(db: InMemoryDatabase) -> None:
    d, st, techs, bays = _ctx(db)
    slot = TimeRange(ist(20, 10), ist(20, 11))
    booked = [_appt("TEC-001", "BAY-01", 10, 60), _appt("TEC-002", "BAY-02", 10, 60, AppointmentStatus.CANCELLED)]
    cap = allocation.capacity(d, st, techs, bays, booked, slot)
    assert (cap.free_technicians, cap.free_bays, cap.capacity) == (2, 3, 2)


def test_choose_prefers_least_loaded_technician_and_best_fit_bay(db: InMemoryDatabase) -> None:
    d, st, techs, bays = _ctx(db)
    booked = [_appt("TEC-001", "BAY-01", 9, 60)]  # TEC-001 already has 60 min today
    chosen = allocation.choose(d, st, techs, bays, booked, TimeRange(ist(20, 13), ist(20, 14)))
    assert chosen is not None
    assert chosen.technician.id == "TEC-002"  # load 0, lowest id among TEC-002/TEC-003
    assert chosen.bay.id == "BAY-01"  # plain LIFT bay before specialised ones


def test_choose_returns_none_when_no_bay(db: InMemoryDatabase) -> None:
    d, st, techs, _ = _ctx(db, "SVC-ALIGN")
    only_rig: list[ServiceBay] = [db.bays["BAY-03"]]
    booked = [_appt("TEC-001", "BAY-03", 10, 60)]
    assert allocation.choose(d, st, techs, only_rig, booked, TimeRange(ist(20, 10), ist(20, 10, 45))) is None


def test_candidate_slots_fit_inside_opening_hours(db: InMemoryDatabase) -> None:
    d = db.dealerships[DEALER]
    slots = allocation.candidate_slots(d, ist(20, 0).date(), timedelta(minutes=180), timedelta(minutes=15))
    assert slots[0].start == ist(20, 8) and slots[-1].end == ist(20, 18)
    assert allocation.candidate_slots(d, ist(25, 0).date(), timedelta(hours=1), timedelta(minutes=15)) == []
