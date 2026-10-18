"""Structured JSON logging, request IDs and Prometheus-format metrics (05-operations/monitoring_v1.0.md).

Metrics are kept dependency-free here for clarity; in production you may swap in
prometheus_client or the OpenTelemetry SDK without touching the routes.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

LATENCY_BUCKETS = (0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.5, 5.0)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "appointment_id", "dealership_id", "method", "path", "status", "duration_ms", "code"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


class Metrics:
    """Thread-safe counters and histograms rendered in Prometheus text format."""

    def __init__(self, service: str) -> None:
        self._service = service
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._hist: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = {}

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        with self._lock:
            self._counters[(name, tuple(sorted(labels.items())))] += value

    def observe(self, name: str, seconds: float, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            # layout: one slot per bucket, then +Inf, then sum
            buckets = self._hist.setdefault(key, [0.0] * (len(LATENCY_BUCKETS) + 2))
            for i, bound in enumerate(LATENCY_BUCKETS):
                if seconds <= bound:
                    buckets[i] += 1
            buckets[-2] += 1
            buckets[-1] += seconds

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"{name}{_fmt(labels, self._service)} {value}")
            for (name, labels), b in sorted(self._hist.items()):
                for i, bound in enumerate(LATENCY_BUCKETS):
                    lines.append(f"{name}_bucket{_fmt(labels, self._service, le=str(bound))} {b[i]}")
                lines.append(f"{name}_bucket{_fmt(labels, self._service, le='+Inf')} {b[-2]}")
                lines.append(f"{name}_count{_fmt(labels, self._service)} {b[-2]}")
                lines.append(f"{name}_sum{_fmt(labels, self._service)} {b[-1]}")
        return "\n".join(lines) + "\n"


def _fmt(labels: tuple[tuple[str, str], ...], service: str, **extra: str) -> str:
    items = [("service", service), *labels, *extra.items()]
    return "{" + ",".join(f'{k}="{v}"' for k, v in items) + "}"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Adds X-Request-ID, access logs and RED metrics for every request."""

    def __init__(self, app: object, metrics: Metrics) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._metrics = metrics
        self._log = logging.getLogger("access")

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")  # templated path keeps label cardinality low
        response.headers["X-Request-ID"] = request_id
        self._metrics.inc("http_requests_total", method=request.method, route=path, status=str(response.status_code))
        self._metrics.observe("http_request_duration_seconds", elapsed, method=request.method, route=path)
        if not path.startswith("/health"):
            self._log.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000, 1),
                },
            )
        return response
