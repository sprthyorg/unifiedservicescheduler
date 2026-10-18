"""Use-case tests, named after the requirement they verify (01-requirements/traceability-matrix_v1.0.csv)."""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import timedelta

import pytest

from app.domain import errors as e
from app.domain.models import AppointmentStatus, ServiceBay, Technician
from app.repositories.memory import InMemoryDatabase, InMemoryUnitOfWork
from app.services.scheduling_service import SchedulingService
from tests.conftest import DEALER, FakeClock, cmd, ist


# ------------------------------------------------------------------ FR-01 resource-constrained booking
def test_fr_01_books_requested_vehicle_service_dealership_and_time(service: SchedulingService) -> None:
    result = service.book_appointment(cmd(ist(20, 10), "SVC-PERIODIC"), "key-0001")
    a = result.appointment
    assert result.created
    assert (a.customer_id, a.vehicle_id, a.dealership_id, a.service_type_id) == (
        "CUS-1001",
        "VEH-5001",
        DEALER,
        "SVC-PERIODIC",
    )
    assert a.start == ist(20, 10) and a.end == ist(20, 13)  # duration taken from the service type
    assert a.status is AppointmentStatus.CONFIRMED


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"dealership": "DLR-NOPE"}, "UNKNOWN_DEALERSHIP"),
        ({"service_type": "SVC-NOPE"}, "UNKNOWN_SERVICE_TYPE"),
        ({"customer": "CUS-NOPE"}, "UNKNOWN_CUSTOMER"),
        ({"vehicle": "VEH-NOPE"}, "UNKNOWN_VEHICLE"),
    ],
)
def test_fr_01_rejects_unknown_references(service: SchedulingService, overrides: dict[str, str], code: str) -> None:
    with pytest.raises(e.UnknownReference) as exc:
        service.book_appointment(cmd(**overrides), "key-0002")  # type: ignore[arg-type]
    assert exc.value.code == code


def test_fr_09_rejects_vehicle_of_another_customer(service: SchedulingService) -> None:
    with pytest.raises(e.VehicleNotOwnedByCustomer):
        service.book_appointment(cmd(vehicle="VEH-5002"), "key-0003")


@pytest.mark.parametrize(
    ("start", "code"),
    [
        (ist(20, 10, 10), "START_TIME_NOT_ALIGNED"),
        (ist(19, 9), "LEAD_TIME_TOO_SHORT"),  # clock is 08:30, min lead 60 min
        (ist(19, 8, 0) + timedelta(days=91), "BEYOND_BOOKING_HORIZON"),
        (ist(20, 7), "OUTSIDE_BUSINESS_HOURS"),
        (ist(20, 17, 30), "OUTSIDE_BUSINESS_HOURS"),  # 60-min job would end 18:30, after closing
        (ist(25, 10), "OUTSIDE_BUSINESS_HOURS"),  # Sunday
    ],
)
def test_fr_09_rejects_invalid_start_times(service: SchedulingService, start, code: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(e.InvalidStartTime) as exc:
        service.book_appointment(cmd(start), "key-0004")
    assert exc.value.code == code


def test_fr_09_vehicle_cannot_hold_overlapping_appointments(service: SchedulingService) -> None:
    service.book_appointment(cmd(ist(20, 10), "SVC-PERIODIC"), "key-0005")
    with pytest.raises(e.VehicleAlreadyBooked):
        service.book_appointment(cmd(ist(20, 11), "SVC-OIL"), "key-0006")


# ------------------------------------------------------------------ FR-02 real-time availability check
def test_fr_02_requires_a_qualified_technician(service: SchedulingService) -> None:
    # Only TEC-003 holds EV_HIGH_VOLTAGE; a second EV job at the same time must be refused.
    first = service.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT"), "key-0101").appointment
    assert first.technician_id == "TEC-003" and first.service_bay_id == "BAY-04"
    with pytest.raises(e.SlotUnavailable):
        service.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT", "CUS-1002", "VEH-5002"), "key-0102")


def test_fr_02_requires_a_compatible_bay(db: InMemoryDatabase, clock: FakeClock) -> None:
    # Two alignment-qualified technicians but only one bay with an alignment rig.
    db.technicians["TEC-004"] = Technician(
        "TEC-004", DEALER, "Extra Aligner", frozenset({"ALIGNMENT"}), db.technicians["TEC-002"].shifts
    )
    svc = SchedulingService(lambda: InMemoryUnitOfWork(db), clock=clock)
    first = svc.book_appointment(cmd(ist(20, 10), "SVC-ALIGN"), "key-0103").appointment
    assert first.service_bay_id == "BAY-03"
    with pytest.raises(e.SlotUnavailable):
        svc.book_appointment(cmd(ist(20, 10, 15), "SVC-ALIGN", "CUS-1002", "VEH-5002"), "key-0104")


def test_fr_02_checks_the_entire_service_duration(service: SchedulingService) -> None:
    # EV job 10:00-11:30 occupies TEC-003; a request starting 11:15 overlaps its tail.
    service.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT"), "key-0105")
    with pytest.raises(e.SlotUnavailable):
        service.book_appointment(cmd(ist(20, 11, 15), "SVC-EV-BATT", "CUS-1002", "VEH-5002"), "key-0106")
    # …but back-to-back is allowed.
    ok = service.book_appointment(cmd(ist(20, 11, 30), "SVC-EV-BATT", "CUS-1002", "VEH-5002"), "key-0107")
    assert ok.appointment.technician_id == "TEC-003"


def test_fr_02_technician_shift_must_cover_duration(service: SchedulingService) -> None:
    # Dealership is open until 18:00 but TEC-003 (only EV tech) finishes at 17:00.
    with pytest.raises(e.SlotUnavailable):
        service.book_appointment(cmd(ist(20, 16), "SVC-EV-BATT"), "key-0108")


def test_fr_02_inactive_resources_are_never_allocated(db: InMemoryDatabase, clock: FakeClock) -> None:
    db.bays["BAY-04"] = replace(db.bays["BAY-04"], active=False)
    svc = SchedulingService(lambda: InMemoryUnitOfWork(db), clock=clock)
    with pytest.raises(e.SlotUnavailable):
        svc.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT"), "key-0109")


def test_fr_02_concurrent_requests_never_double_book(db: InMemoryDatabase, clock: FakeClock) -> None:
    """NFR-05: 20 customers race for the single EV technician at the same time → exactly one wins."""
    for i in range(20):
        db.customers[f"CUS-R{i}"] = replace(db.customers["CUS-1001"], id=f"CUS-R{i}")
        db.vehicles[f"VEH-R{i}"] = replace(
            db.vehicles["VEH-5001"], id=f"VEH-R{i}", customer_id=f"CUS-R{i}", vin=f"VIN{i:014d}"
        )
    svc = SchedulingService(lambda: InMemoryUnitOfWork(db), clock=clock)
    outcomes: list[str] = []
    barrier = threading.Barrier(20)

    def attempt(i: int) -> None:
        barrier.wait()
        try:
            svc.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT", f"CUS-R{i}", f"VEH-R{i}"), f"race-key-{i}")
            outcomes.append("ok")
        except e.SlotUnavailable:
            outcomes.append("conflict")

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("ok") == 1 and outcomes.count("conflict") == 19
    assert len([a for a in db.appointments.values() if a.is_active]) == 1


# ------------------------------------------------------------------ FR-03 confirmed appointment record
def test_fr_03_persists_record_linking_customer_vehicle_technician_and_bay(
    service: SchedulingService, db: InMemoryDatabase
) -> None:
    a = service.book_appointment(cmd(ist(20, 10)), "key-0201").appointment
    stored = service.get_appointment(a.id)
    assert stored == a
    assert stored.technician_id in db.technicians and stored.service_bay_id in db.bays
    assert stored.reference.startswith("APT-") and len(stored.reference) == 12
    assert [ev.type for ev in db.outbox] == ["appointment.confirmed"]
    assert db.outbox[0].payload["technician_id"] == stored.technician_id


def test_fr_03_failed_booking_leaves_no_record(service: SchedulingService, db: InMemoryDatabase) -> None:
    with pytest.raises(e.InvalidStartTime):
        service.book_appointment(cmd(ist(20, 7)), "key-0202")
    assert db.appointments == {} and db.outbox == []


# ------------------------------------------------------------------ FR-04 availability
def test_fr_04_availability_lists_slots_and_shrinks_as_resources_are_booked(service: SchedulingService) -> None:
    _, _, slots = service.availability(DEALER, "SVC-EV-BATT", ist(20, 0).date())
    starts = [s.period.start for s in slots]
    assert starts[0] == ist(20, 8) and starts[-1] == ist(20, 15, 30)  # TEC-003 shift ends 17:00
    service.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT"), "key-0301")
    _, _, after = service.availability(DEALER, "SVC-EV-BATT", ist(20, 0).date())
    taken = {s.period.start for s in after}
    assert ist(20, 10) not in taken and ist(20, 8, 30) in taken and ist(20, 8, 45) not in taken


def test_fr_04_availability_excludes_past_and_lead_time(service: SchedulingService) -> None:
    _, _, slots = service.availability(DEALER, "SVC-OIL", ist(19, 0).date())  # today, clock 08:30
    assert min(s.period.start for s in slots) == ist(19, 9, 30)


# ------------------------------------------------------------------ FR-05 retrieve
def test_fr_05_get_and_list_customer_appointments(service: SchedulingService) -> None:
    a1 = service.book_appointment(cmd(ist(20, 10)), "key-0401").appointment
    a2 = service.book_appointment(cmd(ist(21, 10)), "key-0402").appointment
    assert [a.id for a in service.list_for_customer("CUS-1001")] == [a2.id, a1.id]
    assert service.list_for_customer("CUS-1002") == []
    with pytest.raises(e.AppointmentNotFound):
        service.get_appointment(__import__("uuid").uuid4())


# ------------------------------------------------------------------ FR-06 alternatives
def test_fr_06_conflict_offers_nearest_alternative_slots(service: SchedulingService) -> None:
    service.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT"), "key-0501")
    with pytest.raises(e.SlotUnavailable) as exc:
        service.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT", "CUS-1002", "VEH-5002"), "key-0502")
    alts = exc.value.alternatives
    assert len(alts) == 3
    assert [a.start for a in alts] == [ist(20, 8, 15), ist(20, 8, 30), ist(20, 11, 30)]


# ------------------------------------------------------------------ FR-07 cancel
def test_fr_07_cancel_releases_technician_and_bay(service: SchedulingService, db: InMemoryDatabase) -> None:
    a = service.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT"), "key-0601").appointment
    cancelled = service.cancel_appointment(a.id, customer_id="CUS-1001", reason="plans changed")
    assert cancelled.status is AppointmentStatus.CANCELLED and cancelled.version == 2
    again = service.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT", "CUS-1002", "VEH-5002"), "key-0602")
    assert again.appointment.technician_id == "TEC-003"
    assert [ev.type for ev in db.outbox] == ["appointment.confirmed", "appointment.cancelled", "appointment.confirmed"]


def test_fr_07_cancel_rules(service: SchedulingService, clock: FakeClock) -> None:
    a = service.book_appointment(cmd(ist(20, 10)), "key-0603").appointment
    with pytest.raises(e.AppointmentNotFound):  # someone else's appointment looks like a missing one
        service.cancel_appointment(a.id, customer_id="CUS-1002")
    first = service.cancel_appointment(a.id, customer_id="CUS-1001")
    assert service.cancel_appointment(a.id, customer_id="CUS-1001") == first  # idempotent
    b = service.book_appointment(cmd(ist(21, 10)), "key-0604").appointment
    clock.now = ist(21, 10)
    with pytest.raises(e.CancellationWindowClosed):
        service.cancel_appointment(b.id, customer_id="CUS-1001")


# ------------------------------------------------------------------ FR-08 idempotency
def test_fr_08_same_key_same_request_returns_original(service: SchedulingService, db: InMemoryDatabase) -> None:
    first = service.book_appointment(cmd(ist(20, 10)), "key-0701")
    replay = service.book_appointment(cmd(ist(20, 10)), "key-0701")
    assert replay.appointment == first.appointment and not replay.created
    assert len(db.appointments) == 1 and len(db.outbox) == 1


def test_fr_08_same_key_different_request_is_rejected(service: SchedulingService) -> None:
    service.book_appointment(cmd(ist(20, 10)), "key-0702")
    with pytest.raises(e.IdempotencyKeyReused):
        service.book_appointment(cmd(ist(20, 11)), "key-0702")


def test_fr_08_replay_still_works_after_slot_has_passed(service: SchedulingService, clock: FakeClock) -> None:
    first = service.book_appointment(cmd(ist(20, 10)), "key-0703")
    clock.now = ist(20, 12)
    assert service.book_appointment(cmd(ist(20, 10)), "key-0703").appointment == first.appointment


def test_fr_02_other_dealerships_bays_are_never_allocated(db: InMemoryDatabase, clock: FakeClock) -> None:
    db.bays["BAY-99"] = ServiceBay("BAY-99", "OTHER-DEALER", "Foreign bay", frozenset({"EV_SAFE"}))
    svc = SchedulingService(lambda: InMemoryUnitOfWork(db), clock=clock)
    a = svc.book_appointment(cmd(ist(20, 10), "SVC-EV-BATT"), "key-0801").appointment
    assert a.service_bay_id == "BAY-04"  # never another dealership's bay
