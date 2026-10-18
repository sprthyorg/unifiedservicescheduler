"""Map domain errors to RFC 9457 problem+json responses."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain import errors as e

_STATUS: dict[type[e.DomainError], int] = {
    e.UnknownReference: 422,
    e.VehicleNotOwnedByCustomer: 422,
    e.InvalidStartTime: 422,
    e.SlotUnavailable: 409,
    e.VehicleAlreadyBooked: 409,
    e.IdempotencyKeyReused: 409,
    e.InvalidTransition: 409,
    e.CancellationWindowClosed: 409,
    e.ConcurrentModification: 409,
    e.AppointmentNotFound: 404,
}

_log = logging.getLogger("errors")


def problem(status: int, title: str, detail: str, code: str, instance: str, **extra: Any) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"https://errors.scheduler.example/{code.lower().replace('_', '-')}",
            "title": title,
            "status": status,
            "detail": detail,
            "code": code,
            "instance": instance,
            **extra,
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(e.DomainError)
    async def _domain(request: Request, exc: e.DomainError) -> JSONResponse:
        status = _STATUS.get(type(exc), 400)
        _log.info("domain error", extra={"code": exc.code, "path": request.url.path})
        if request.url.path == "/v1/appointments" and request.method == "POST":
            request.app.state.metrics.inc("scheduler_booking_rejections_total", code=exc.code)
        extra: dict[str, Any] = {}
        if isinstance(exc, e.SlotUnavailable):
            extra["alternatives"] = [
                {"start_time": s.start.isoformat(), "end_time": s.end.isoformat()} for s in exc.alternatives
            ]
        return problem(status, exc.code.replace("_", " ").title(), exc.detail, exc.code, request.url.path, **extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors())
        return problem(422, "Validation Failed", detail, "VALIDATION_FAILED", request.url.path)

    @app.exception_handler(ValueError)
    async def _value(request: Request, exc: ValueError) -> JSONResponse:
        return problem(400, "Bad Request", str(exc), "BAD_REQUEST", request.url.path)
