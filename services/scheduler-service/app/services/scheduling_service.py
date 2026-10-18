"""Application service: the three core use cases plus availability, lookup and cancellation.

FR-01 book_appointment · FR-02 resource check (inside book_appointment) · FR-03 persistent record
FR-04 availability · FR-05 retrieve · FR-06 alternatives on conflict · FR-07 cancel · FR-08 idempotency
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.domain import allocation
from app.domain import errors as e
from app.domain.events import appointment_cancelled, appointment_confirmed
from app.domain.models import Appointment, AppointmentStatus, Dealership, ServiceType, TimeRange
from app.domain.ports import UnitOfWork

_log = logging.getLogger("scheduling")


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class BookingPolicy:
    slot_granularity: timedelta = timedelta(minutes=15)
    min_lead_time: timedelta = timedelta(minutes=60)
    horizon: timedelta = timedelta(days=90)
    alternatives_count: int = 3
    alternatives_search_days: int = 7


@dataclass(frozen=True)
class BookAppointmentCommand:
    customer_id: str
    vehicle_id: str
    dealership_id: str
    service_type_id: str
    desired_start: datetime
    notes: str | None = None

    def fingerprint(self) -> str:
        """Stable hash of the request, used to detect Idempotency-Key reuse with a different body."""
        canonical = json.dumps(
            {
                "customer_id": self.customer_id,
                "vehicle_id": self.vehicle_id,
                "dealership_id": self.dealership_id,
                "service_type_id": self.service_type_id,
                "desired_start": self.desired_start.astimezone(UTC).isoformat(),
                "notes": self.notes,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class BookingResult:
    appointment: Appointment
    created: bool  # False → idempotent replay of an earlier successful request


class SchedulingService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        policy: BookingPolicy | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._uow = uow_factory
        self._policy = policy or BookingPolicy()
        self._now = clock

    # ------------------------------------------------------------------------------------------
    # FR-01 / FR-02 / FR-03 / FR-06 / FR-08
    # ------------------------------------------------------------------------------------------
    def book_appointment(self, cmd: BookAppointmentCommand, idempotency_key: str) -> BookingResult:
        if cmd.desired_start.tzinfo is None:
            raise ValueError("desired_start must include a UTC offset")
        fingerprint = cmd.fingerprint()
        with self._uow() as uow:
            ref = uow.reference
            dealership = ref.dealership(cmd.dealership_id)
            if dealership is None:
                raise e.UnknownReference(f"dealership '{cmd.dealership_id}' not found", code="UNKNOWN_DEALERSHIP")
            service_type = ref.service_type(cmd.service_type_id)
            if service_type is None or not service_type.active:
                raise e.UnknownReference(f"service type '{cmd.service_type_id}' not found", code="UNKNOWN_SERVICE_TYPE")
            if ref.customer(cmd.customer_id) is None:
                raise e.UnknownReference(f"customer '{cmd.customer_id}' not found", code="UNKNOWN_CUSTOMER")
            vehicle = ref.vehicle(cmd.vehicle_id)
            if vehicle is None:
                raise e.UnknownReference(f"vehicle '{cmd.vehicle_id}' not found", code="UNKNOWN_VEHICLE")
            if vehicle.customer_id != cmd.customer_id:
                raise e.VehicleNotOwnedByCustomer(f"vehicle '{vehicle.id}' is not registered to this customer")

            # Everything below reads and writes resource schedules → serialise per dealership (ADR-002).
            uow.lock_dealership(dealership.id)

            existing = uow.appointments.by_idempotency_key(cmd.customer_id, idempotency_key)
            if existing is not None:
                if existing.request_hash != fingerprint:
                    raise e.IdempotencyKeyReused("Idempotency-Key was already used with a different request")
                return BookingResult(existing, created=False)

            now = self._now()
            slot = TimeRange(cmd.desired_start, cmd.desired_start + service_type.duration)
            self._validate_start(dealership, slot, now)

            if uow.appointments.confirmed_for_vehicle(vehicle.id, slot):
                raise e.VehicleAlreadyBooked("vehicle already has an appointment overlapping this time")

            day = dealership.local_date(slot.start)
            booked = uow.appointments.confirmed_in_range(dealership.id, dealership.day_bounds(day))
            technicians = ref.technicians(dealership.id)
            bays = ref.bays(dealership.id)
            chosen = allocation.choose(dealership, service_type, technicians, bays, booked, slot)
            if chosen is None:
                alternatives = self._alternatives(uow, dealership, service_type, slot, now)
                _log.info(
                    "slot unavailable",
                    extra={"dealership_id": dealership.id, "code": "SLOT_UNAVAILABLE"},
                )
                raise e.SlotUnavailable(
                    "no qualified technician and compatible service bay are both free for the full duration",
                    alternatives=alternatives,
                )

            appointment = Appointment.confirm(
                customer_id=cmd.customer_id,
                vehicle_id=vehicle.id,
                dealership_id=dealership.id,
                service_type_id=service_type.id,
                technician_id=chosen.technician.id,
                service_bay_id=chosen.bay.id,
                period=slot,
                idempotency_key=idempotency_key,
                request_hash=fingerprint,
                now=now,
                notes=cmd.notes,
            )
            uow.appointments.add(appointment)
            uow.outbox.add(appointment_confirmed(appointment))
            uow.commit()
        _log.info(
            "appointment confirmed",
            extra={"appointment_id": str(appointment.id), "dealership_id": appointment.dealership_id},
        )
        return BookingResult(appointment, created=True)

    def _validate_start(self, dealership: Dealership, slot: TimeRange, now: datetime) -> None:
        p = self._policy
        local = slot.start.astimezone(dealership.tz)
        step = int(p.slot_granularity.total_seconds() // 60)
        if local.second or local.microsecond or local.minute % step:
            raise e.InvalidStartTime(
                f"start time must be aligned to {step}-minute slots", code="START_TIME_NOT_ALIGNED"
            )
        if slot.start < now + p.min_lead_time:
            raise e.InvalidStartTime(
                f"appointments must be booked at least {int(p.min_lead_time.total_seconds() // 60)} minutes ahead",
                code="LEAD_TIME_TOO_SHORT",
            )
        if slot.start > now + p.horizon:
            raise e.InvalidStartTime(
                f"appointments can be booked at most {p.horizon.days} days ahead", code="BEYOND_BOOKING_HORIZON"
            )
        if not allocation.within_opening_hours(dealership, slot):
            raise e.InvalidStartTime(
                "the full service duration must fall within dealership opening hours",
                code="OUTSIDE_BUSINESS_HOURS",
            )

    # ------------------------------------------------------------------------------------------
    # FR-04 availability / FR-06 alternatives
    # ------------------------------------------------------------------------------------------
    def availability(
        self, dealership_id: str, service_type_id: str, day: date
    ) -> tuple[Dealership, ServiceType, list[allocation.SlotCapacity]]:
        with self._uow() as uow:
            dealership = uow.reference.dealership(dealership_id)
            if dealership is None:
                raise e.UnknownReference(f"dealership '{dealership_id}' not found", code="UNKNOWN_DEALERSHIP")
            service_type = uow.reference.service_type(service_type_id)
            if service_type is None or not service_type.active:
                raise e.UnknownReference(f"service type '{service_type_id}' not found", code="UNKNOWN_SERVICE_TYPE")
            slots = self._open_slots(uow, dealership, service_type, day, self._now())
        return dealership, service_type, slots

    def _open_slots(
        self, uow: UnitOfWork, dealership: Dealership, service_type: ServiceType, day: date, now: datetime
    ) -> list[allocation.SlotCapacity]:
        p = self._policy
        candidates = [
            s
            for s in allocation.candidate_slots(dealership, day, service_type.duration, p.slot_granularity)
            if now + p.min_lead_time <= s.start <= now + p.horizon
        ]
        if not candidates:
            return []
        booked = uow.appointments.confirmed_in_range(dealership.id, dealership.day_bounds(day))
        technicians = uow.reference.technicians(dealership.id)
        bays = uow.reference.bays(dealership.id)
        result = []
        for slot in candidates:
            cap = allocation.capacity(dealership, service_type, technicians, bays, booked, slot)
            if cap.capacity > 0:
                result.append(cap)
        return result

    def _alternatives(
        self, uow: UnitOfWork, dealership: Dealership, service_type: ServiceType, wanted: TimeRange, now: datetime
    ) -> list[TimeRange]:
        """Closest bookable slots to the requested start, searching the next N days (FR-06)."""
        p = self._policy
        if p.alternatives_count <= 0:
            return []
        first_day = dealership.local_date(max(wanted.start, now))
        found: list[TimeRange] = []
        for offset in range(p.alternatives_search_days):
            found += [
                c.period for c in self._open_slots(uow, dealership, service_type, first_day + timedelta(offset), now)
            ]
            if len(found) >= p.alternatives_count and offset > 0:
                break
        found.sort(key=lambda s: (abs((s.start - wanted.start).total_seconds()), s.start))
        return sorted(found[: p.alternatives_count])

    # ------------------------------------------------------------------------------------------
    # Reference data (read-only)
    # ------------------------------------------------------------------------------------------
    def list_dealerships(self) -> Sequence[Dealership]:
        with self._uow() as uow:
            return uow.reference.list_dealerships()

    def list_service_types(self) -> Sequence[ServiceType]:
        with self._uow() as uow:
            return uow.reference.list_service_types()

    # ------------------------------------------------------------------------------------------
    # FR-05 retrieve / FR-07 cancel
    # ------------------------------------------------------------------------------------------
    def get_appointment(self, appointment_id: uuid.UUID) -> Appointment:
        with self._uow() as uow:
            a = uow.appointments.get(appointment_id)
        if a is None:
            raise e.AppointmentNotFound(f"appointment '{appointment_id}' not found")
        return a

    def list_for_customer(self, customer_id: str, limit: int = 50) -> Sequence[Appointment]:
        with self._uow() as uow:
            return uow.appointments.list_for_customer(customer_id, limit)

    def cancel_appointment(
        self, appointment_id: uuid.UUID, *, customer_id: str, reason: str | None = None
    ) -> Appointment:
        with self._uow() as uow:
            current = uow.appointments.get(appointment_id)
            # Not-yours is reported as not-found so appointment ids cannot be probed (NFR-08).
            if current is None or current.customer_id != customer_id:
                raise e.AppointmentNotFound(f"appointment '{appointment_id}' not found")
            if current.status is AppointmentStatus.CANCELLED:
                return current  # cancelling twice is a no-op (idempotent)
            cancelled = current.cancel(now=self._now(), reason=reason)
            uow.appointments.update(cancelled, expected_version=current.version)
            uow.outbox.add(appointment_cancelled(cancelled))
            uow.commit()
        _log.info("appointment cancelled", extra={"appointment_id": str(cancelled.id)})
        return cancelled
