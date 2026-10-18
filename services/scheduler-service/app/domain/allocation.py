"""Pure resource-allocation rules (FR-02, ADR-003). No I/O — the service layer supplies the data.

A slot is bookable when, for the *entire* [start, end) interval:
  * the dealership is open,
  * at least one active technician who holds the required skill is on shift and has no overlapping
    CONFIRMED appointment, and
  * at least one active bay with the required capability has no overlapping CONFIRMED appointment.

Technicians and bays are independent pools (any qualified technician can work in any compatible
bay), so the number of parallel bookings a slot can still take is min(free technicians, free bays).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.domain.models import (
    Appointment,
    Dealership,
    ServiceBay,
    ServiceType,
    Technician,
    TimeRange,
    window_on,
)


@dataclass(frozen=True)
class Allocation:
    technician: Technician
    bay: ServiceBay


@dataclass(frozen=True)
class SlotCapacity:
    period: TimeRange
    free_technicians: int
    free_bays: int

    @property
    def capacity(self) -> int:
        return min(self.free_technicians, self.free_bays)


def within_opening_hours(dealership: Dealership, slot: TimeRange) -> bool:
    day = dealership.local_date(slot.start)
    window = window_on(dealership.opening_hours, day, dealership.tz)
    return window is not None and window.contains(slot)


def _busy_ids(booked: Iterable[Appointment], slot: TimeRange, attr: str) -> set[str]:
    return {getattr(a, attr) for a in booked if a.is_active and a.period.overlaps(slot)}


def free_technicians(
    dealership: Dealership,
    service_type: ServiceType,
    technicians: Iterable[Technician],
    booked: Iterable[Appointment],
    slot: TimeRange,
) -> list[Technician]:
    booked = list(booked)
    busy = _busy_ids(booked, slot, "technician_id")
    day = dealership.local_date(slot.start)
    result = []
    for t in technicians:
        if not t.active or t.dealership_id != dealership.id or service_type.required_skill not in t.skills:
            continue
        shift = window_on(t.shifts, day, dealership.tz)
        if shift is None or not shift.contains(slot) or t.id in busy:
            continue
        result.append(t)
    return result


def free_bays(
    dealership: Dealership,
    service_type: ServiceType,
    bays: Iterable[ServiceBay],
    booked: Iterable[Appointment],
    slot: TimeRange,
) -> list[ServiceBay]:
    busy = _busy_ids(booked, slot, "service_bay_id")
    return [
        b
        for b in bays
        if b.active
        and b.dealership_id == dealership.id
        and service_type.required_bay_capability in b.capabilities
        and b.id not in busy
    ]


def capacity(
    dealership: Dealership,
    service_type: ServiceType,
    technicians: Sequence[Technician],
    bays: Sequence[ServiceBay],
    booked: Sequence[Appointment],
    slot: TimeRange,
) -> SlotCapacity:
    return SlotCapacity(
        slot,
        len(free_technicians(dealership, service_type, technicians, booked, slot)),
        len(free_bays(dealership, service_type, bays, booked, slot)),
    )


def choose(
    dealership: Dealership,
    service_type: ServiceType,
    technicians: Sequence[Technician],
    bays: Sequence[ServiceBay],
    booked: Sequence[Appointment],
    slot: TimeRange,
) -> Allocation | None:
    """Pick one technician and one bay, or None if the slot cannot be served.

    `booked` must contain every CONFIRMED appointment of the dealership on the slot's local day,
    so that technician load can be balanced.

    Policy (ADR-003): least-loaded technician that day (minutes booked), then lowest id;
    best-fit bay (fewest capabilities, keeps specialised bays free), then lowest id. Deterministic.
    """
    techs = free_technicians(dealership, service_type, technicians, booked, slot)
    free = free_bays(dealership, service_type, bays, booked, slot)
    if not techs or not free:
        return None
    load: dict[str, int] = defaultdict(int)
    for a in booked:
        if a.is_active:
            load[a.technician_id] += a.period.minutes
    tech = min(techs, key=lambda t: (load[t.id], t.id))
    bay = min(free, key=lambda b: (len(b.capabilities), b.id))
    return Allocation(tech, bay)


def candidate_slots(dealership: Dealership, day: date, duration: timedelta, granularity: timedelta) -> list[TimeRange]:
    """All aligned start times on `day` whose full duration fits inside opening hours."""
    window = window_on(dealership.opening_hours, day, dealership.tz)
    if window is None:
        return []
    slots: list[TimeRange] = []
    start: datetime = window.start
    while start + duration <= window.end:
        slots.append(TimeRange(start, start + duration))
        start += granularity
    return slots
