"""Domain errors. Each carries a stable machine-readable `code` (04-design/api/.../openapi_1.0.0.yaml)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class DomainError(Exception):
    code = "DOMAIN_ERROR"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


# --- 422: request is well-formed but cannot be accepted -------------------------------------------
class UnknownReference(DomainError):
    """A referenced dealership / service type / customer / vehicle does not exist (or is inactive)."""

    code = "UNKNOWN_REFERENCE"


class VehicleNotOwnedByCustomer(DomainError):
    code = "VEHICLE_NOT_OWNED_BY_CUSTOMER"


class InvalidStartTime(DomainError):
    """Codes: START_TIME_NOT_ALIGNED, LEAD_TIME_TOO_SHORT, BEYOND_BOOKING_HORIZON, OUTSIDE_BUSINESS_HOURS."""

    code = "INVALID_START_TIME"


# --- 409: conflicts with current state ----------------------------------------------------------
class SlotUnavailable(DomainError):
    """No qualified technician + compatible bay are both free for the full duration (FR-02)."""

    code = "SLOT_UNAVAILABLE"

    def __init__(self, detail: str, alternatives: Sequence[Any] = ()) -> None:
        super().__init__(detail)
        self.alternatives = list(alternatives)


class VehicleAlreadyBooked(DomainError):
    code = "VEHICLE_ALREADY_BOOKED"


class IdempotencyKeyReused(DomainError):
    code = "IDEMPOTENCY_KEY_REUSED"


class InvalidTransition(DomainError):
    code = "INVALID_STATE_TRANSITION"


class CancellationWindowClosed(DomainError):
    code = "CANCELLATION_WINDOW_CLOSED"


class ConcurrentModification(DomainError):
    code = "CONCURRENT_MODIFICATION"


# --- 404 ----------------------------------------------------------------------------------------
class AppointmentNotFound(DomainError):
    code = "APPOINTMENT_NOT_FOUND"
