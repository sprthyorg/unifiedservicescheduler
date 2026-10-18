"""Domain entities and value objects (04-design/data-model/data-model_v1.0.md)."""

from __future__ import annotations

import base64
import enum
import hashlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.errors import CancellationWindowClosed, InvalidTransition


# --------------------------------------------------------------------------------------------------
# Value objects
# --------------------------------------------------------------------------------------------------
@dataclass(frozen=True, order=True)
class TimeRange:
    """Half-open interval [start, end) in absolute (timezone-aware) time."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("TimeRange requires timezone-aware datetimes")
        if self.end <= self.start:
            raise ValueError("TimeRange end must be after start")

    def overlaps(self, other: TimeRange) -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: TimeRange) -> bool:
        return self.start <= other.start and other.end <= self.end

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass(frozen=True)
class DailyWindow:
    """Local wall-clock opening/shift window for one ISO weekday (1 = Monday … 7 = Sunday)."""

    opens: time
    closes: time

    def __post_init__(self) -> None:
        if self.closes <= self.opens:
            raise ValueError("DailyWindow must close after it opens (overnight windows are out of scope, A-09)")

    def on(self, day: date, tz: ZoneInfo) -> TimeRange:
        return TimeRange(datetime.combine(day, self.opens, tzinfo=tz), datetime.combine(day, self.closes, tzinfo=tz))


WeeklySchedule = Mapping[int, DailyWindow]


def window_on(schedule: WeeklySchedule, day: date, tz: ZoneInfo) -> TimeRange | None:
    w = schedule.get(day.isoweekday())
    return w.on(day, tz) if w else None


# --------------------------------------------------------------------------------------------------
# Reference data (owned by dealer-management / CRM upstreams, replicated read-only — A-03)
# --------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Dealership:
    id: str
    name: str
    timezone: str
    opening_hours: WeeklySchedule

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def local_date(self, instant: datetime) -> date:
        return instant.astimezone(self.tz).date()

    def day_bounds(self, day: date) -> TimeRange:
        start = datetime.combine(day, time.min, tzinfo=self.tz)
        return TimeRange(start, datetime.combine(day + timedelta(days=1), time.min, tzinfo=self.tz))


@dataclass(frozen=True)
class ServiceType:
    id: str
    name: str
    duration_minutes: int
    required_skill: str
    required_bay_capability: str
    active: bool = True

    @property
    def duration(self) -> timedelta:
        return timedelta(minutes=self.duration_minutes)


@dataclass(frozen=True)
class ServiceBay:
    id: str
    dealership_id: str
    name: str
    capabilities: frozenset[str]
    active: bool = True


@dataclass(frozen=True)
class Technician:
    id: str
    dealership_id: str
    name: str
    skills: frozenset[str]
    shifts: WeeklySchedule = field(default_factory=dict)
    active: bool = True


@dataclass(frozen=True)
class Customer:
    id: str
    display_name: str


@dataclass(frozen=True)
class Vehicle:
    id: str
    customer_id: str
    vin: str
    make: str
    model: str
    model_year: int


# --------------------------------------------------------------------------------------------------
# Aggregate: Appointment
# --------------------------------------------------------------------------------------------------
class AppointmentStatus(enum.StrEnum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


def new_reference(appointment_id: uuid.UUID) -> str:
    """Short, human-friendly, non-sequential booking reference, e.g. APT-K3Q7M2XA."""
    digest = hashlib.sha256(appointment_id.bytes).digest()
    return "APT-" + base64.b32encode(digest).decode()[:8]


@dataclass(frozen=True)
class Appointment:
    id: uuid.UUID
    reference: str
    customer_id: str
    vehicle_id: str
    dealership_id: str
    service_type_id: str
    technician_id: str
    service_bay_id: str
    start: datetime
    end: datetime
    status: AppointmentStatus
    idempotency_key: str
    request_hash: str
    created_at: datetime
    updated_at: datetime
    version: int = 1
    notes: str | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None

    @property
    def period(self) -> TimeRange:
        return TimeRange(self.start, self.end)

    @property
    def is_active(self) -> bool:
        return self.status is AppointmentStatus.CONFIRMED

    @classmethod
    def confirm(
        cls,
        *,
        customer_id: str,
        vehicle_id: str,
        dealership_id: str,
        service_type_id: str,
        technician_id: str,
        service_bay_id: str,
        period: TimeRange,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
        notes: str | None = None,
    ) -> Appointment:
        appointment_id = uuid.uuid4()
        return cls(
            id=appointment_id,
            reference=new_reference(appointment_id),
            customer_id=customer_id,
            vehicle_id=vehicle_id,
            dealership_id=dealership_id,
            service_type_id=service_type_id,
            technician_id=technician_id,
            service_bay_id=service_bay_id,
            start=period.start.astimezone(UTC),  # persisted and returned in UTC (A-10)
            end=period.end.astimezone(UTC),
            status=AppointmentStatus.CONFIRMED,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            created_at=now,
            updated_at=now,
            notes=notes,
        )

    def cancel(self, *, now: datetime, reason: str | None) -> Appointment:
        if self.status is not AppointmentStatus.CONFIRMED:
            raise InvalidTransition(f"appointment is {self.status.value}; only CONFIRMED can be cancelled")
        if now >= self.start:
            raise CancellationWindowClosed("appointment has already started")
        return replace(
            self,
            status=AppointmentStatus.CANCELLED,
            cancelled_at=now,
            cancellation_reason=reason,
            updated_at=now,
            version=self.version + 1,
        )
