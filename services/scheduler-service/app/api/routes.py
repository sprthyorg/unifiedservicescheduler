"""HTTP routes. Each handler names the requirement it implements."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, Response, status

from app.api.schemas import (
    AppointmentList,
    AppointmentResponse,
    AvailabilityResponse,
    BookAppointmentRequest,
    CancelAppointmentRequest,
    DealershipResponse,
    ServiceTypeResponse,
)
from app.domain.errors import DomainError
from app.services.scheduling_service import BookAppointmentCommand, SchedulingService

router = APIRouter(prefix="/v1")

IdempotencyKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=8, max_length=128, description="Client-generated unique key (UUID)"),
]


def _svc(request: Request) -> SchedulingService:
    svc: SchedulingService = request.app.state.scheduling_service
    return svc


@router.post(
    "/appointments",
    status_code=status.HTTP_201_CREATED,
    response_model=AppointmentResponse,
    tags=["appointments"],
    summary="Book a service appointment (FR-01, FR-02, FR-03, FR-06, FR-08)",
)
def book_appointment(
    body: BookAppointmentRequest, request: Request, response: Response, idempotency_key: IdempotencyKey = None
) -> AppointmentResponse:
    if not idempotency_key:
        raise DomainError("Idempotency-Key header is required", code="IDEMPOTENCY_KEY_REQUIRED")
    result = _svc(request).book_appointment(
        BookAppointmentCommand(
            customer_id=body.customer_id,
            vehicle_id=body.vehicle_id,
            dealership_id=body.dealership_id,
            service_type_id=body.service_type_id,
            desired_start=body.desired_start_time,
            notes=body.notes,
        ),
        idempotency_key,
    )
    response.headers["Location"] = f"/v1/appointments/{result.appointment.id}"
    if result.created:
        request.app.state.metrics.inc("scheduler_appointments_confirmed_total", dealership_id=body.dealership_id)
    else:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return AppointmentResponse.of(result.appointment)


@router.get(
    "/appointments/{appointment_id}",
    response_model=AppointmentResponse,
    tags=["appointments"],
    summary="Get an appointment (FR-05)",
)
def get_appointment(appointment_id: uuid.UUID, request: Request) -> AppointmentResponse:
    return AppointmentResponse.of(_svc(request).get_appointment(appointment_id))


@router.get(
    "/appointments",
    response_model=AppointmentList,
    tags=["appointments"],
    summary="List a customer's appointments, newest first (FR-05)",
)
def list_appointments(
    request: Request,
    customer_id: Annotated[str, Query(min_length=1, max_length=64)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AppointmentList:
    items = _svc(request).list_for_customer(customer_id, limit)
    return AppointmentList(items=[AppointmentResponse.of(a) for a in items])


@router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    tags=["appointments"],
    summary="Cancel an appointment and release its technician and bay (FR-07)",
)
def cancel_appointment(
    appointment_id: uuid.UUID, body: CancelAppointmentRequest, request: Request
) -> AppointmentResponse:
    cancelled = _svc(request).cancel_appointment(appointment_id, customer_id=body.customer_id, reason=body.reason)
    return AppointmentResponse.of(cancelled)


@router.get(
    "/availability",
    response_model=AvailabilityResponse,
    tags=["availability"],
    summary="Bookable start times for a service type at a dealership on a date (FR-04)",
)
def availability(
    request: Request,
    dealership_id: Annotated[str, Query(min_length=1, max_length=64)],
    service_type_id: Annotated[str, Query(min_length=1, max_length=64)],
    on: Annotated[date, Query(alias="date", description="Dealership-local date, YYYY-MM-DD")],
) -> AvailabilityResponse:
    d, st, slots = _svc(request).availability(dealership_id, service_type_id, on)
    return AvailabilityResponse.of(d, st, on, slots)


@router.get("/dealerships", response_model=list[DealershipResponse], tags=["reference"], summary="List dealerships")
def list_dealerships(request: Request) -> list[DealershipResponse]:
    return [DealershipResponse(id=d.id, name=d.name, timezone=d.timezone) for d in _svc(request).list_dealerships()]


@router.get(
    "/service-types", response_model=list[ServiceTypeResponse], tags=["reference"], summary="List service types"
)
def list_service_types(request: Request) -> list[ServiceTypeResponse]:
    return [
        ServiceTypeResponse(
            id=s.id,
            name=s.name,
            duration_minutes=s.duration_minutes,
            required_skill=s.required_skill,
            required_bay_capability=s.required_bay_capability,
        )
        for s in _svc(request).list_service_types()
    ]
