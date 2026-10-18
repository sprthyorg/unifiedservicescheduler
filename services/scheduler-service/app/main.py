"""Application factory and wiring (composition root)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app import __version__
from app.api.errors import register_error_handlers
from app.api.routes import router
from app.config import Settings
from app.domain.ports import UnitOfWork
from app.observability import Metrics, RequestContextMiddleware, configure_logging
from app.services.scheduling_service import BookingPolicy, SchedulingService, utcnow
from app.wiring import Pingable, build_storage


def create_app(
    settings: Settings | None = None,
    *,
    uow_factory: Callable[[], UnitOfWork] | None = None,
    database: Pingable | None = None,
    clock: Callable[[], datetime] = utcnow,
) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)

    if uow_factory is None or database is None:
        database, uow_factory = build_storage(settings)

    app = FastAPI(
        title="Unified Service Scheduler — scheduler-service",
        version=__version__,
        description="Service-appointment booking API — see 04-design/api/scheduler-service/v1/openapi_1.0.0.yaml",
    )
    metrics = Metrics(settings.service_name)
    app.state.metrics = metrics
    app.state.database = database
    app.state.scheduling_service = SchedulingService(
        uow_factory,
        policy=BookingPolicy(
            slot_granularity=timedelta(minutes=settings.slot_granularity_minutes),
            min_lead_time=timedelta(minutes=settings.min_lead_time_minutes),
            horizon=timedelta(days=settings.booking_horizon_days),
            alternatives_count=settings.alternatives_count,
            alternatives_search_days=settings.alternatives_search_days,
        ),
        clock=clock,
    )

    app.add_middleware(RequestContextMiddleware, metrics=metrics)
    register_error_handlers(app)
    app.include_router(router)

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def ready(request: Request) -> JSONResponse:
        ok = request.app.state.database.ping()
        return JSONResponse({"status": "ok" if ok else "unavailable"}, status_code=200 if ok else 503)

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.app.state.metrics.render(), media_type="text/plain; version=0.0.4")

    return app


app = create_app()
