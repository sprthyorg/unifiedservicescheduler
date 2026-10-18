"""HTTP request/response models (contract: 04-design/api/scheduler-service/v1/openapi_1.0.0.yaml)."""

from __future__ import annotations

import datetime as dt
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.domain.allocation import SlotCapacity
from app.domain.models import Appointment, Dealership, ServiceType

Id = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class BookAppointmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: Id
    vehicle_id: Id
    dealership_id: Id
    service_type_id: Id
    desired_start_time: AwareDatetime = Field(description="ISO-8601 with UTC offset, e.g. 2026-10-20T10:00:00+05:30")
    notes: str | None = Field(default=None, max_length=500)


class CancelAppointmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: Id
    reason: str | None = Field(default=None, max_length=500)


class AppointmentResponse(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    customer_id: str
    vehicle_id: str
    dealership_id: str
    service_type_id: str
    technician_id: str
    service_bay_id: str
    start_time: datetime
    end_time: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None
    cancellation_reason: str | None
    version: int

    @classmethod
    def of(cls, a: Appointment) -> AppointmentResponse:
        return cls(
            id=a.id,
            reference=a.reference,
            status=a.status.value,
            customer_id=a.customer_id,
            vehicle_id=a.vehicle_id,
            dealership_id=a.dealership_id,
            service_type_id=a.service_type_id,
            technician_id=a.technician_id,
            service_bay_id=a.service_bay_id,
            start_time=a.start,
            end_time=a.end,
            notes=a.notes,
            created_at=a.created_at,
            updated_at=a.updated_at,
            cancelled_at=a.cancelled_at,
            cancellation_reason=a.cancellation_reason,
            version=a.version,
        )


class AppointmentList(BaseModel):
    items: list[AppointmentResponse]


class Slot(BaseModel):
    start_time: datetime
    end_time: datetime


class AvailableSlot(Slot):
    capacity: int = Field(description="How many more appointments of this type can start at this time")


class AvailabilityResponse(BaseModel):
    dealership_id: str
    service_type_id: str
    date: dt.date
    timezone: str
    duration_minutes: int
    slots: list[AvailableSlot]

    @classmethod
    def of(cls, d: Dealership, st: ServiceType, day: dt.date, slots: list[SlotCapacity]) -> AvailabilityResponse:
        z = d.tz
        return cls(
            dealership_id=d.id,
            service_type_id=st.id,
            date=day,
            timezone=d.timezone,
            duration_minutes=st.duration_minutes,
            slots=[
                AvailableSlot(
                    start_time=s.period.start.astimezone(z), end_time=s.period.end.astimezone(z), capacity=s.capacity
                )
                for s in slots
            ],
        )


class DealershipResponse(BaseModel):
    id: str
    name: str
    timezone: str


class ServiceTypeResponse(BaseModel):
    id: str
    name: str
    duration_minutes: int
    required_skill: str
    required_bay_capability: str
