"""Domain events written to the transactional outbox (ADR-004, 04-design/events/)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.models import Appointment


@dataclass(frozen=True)
class DomainEvent:
    type: str
    aggregate_id: uuid.UUID
    occurred_at: datetime
    payload: dict[str, Any]
    schema_version: int = 1
    id: uuid.UUID = field(default_factory=uuid.uuid4)


def _body(a: Appointment) -> dict[str, Any]:
    return {
        "appointment_id": str(a.id),
        "reference": a.reference,
        "customer_id": a.customer_id,
        "vehicle_id": a.vehicle_id,
        "dealership_id": a.dealership_id,
        "service_type_id": a.service_type_id,
        "technician_id": a.technician_id,
        "service_bay_id": a.service_bay_id,
        "start_time": a.start.isoformat(),
        "end_time": a.end.isoformat(),
        "status": a.status.value,
        "version": a.version,
    }


def appointment_confirmed(a: Appointment) -> DomainEvent:
    return DomainEvent("appointment.confirmed", a.id, a.created_at, _body(a))


def appointment_cancelled(a: Appointment) -> DomainEvent:
    body = _body(a) | {"cancellation_reason": a.cancellation_reason}
    return DomainEvent("appointment.cancelled", a.id, a.updated_at, body)
