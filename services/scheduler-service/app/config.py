"""12-factor configuration: everything from environment variables with safe local defaults.

Booking-policy defaults are the values agreed in 01-requirements/assumptions_v1.0.md (A-05..A-08).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    service_name: str = "scheduler-service"
    environment: str = "local"
    database_url: str | None = None  # unset → in-memory store (local/dev/tests)
    db_pool_max_size: int = 10
    seed_demo_data: bool = False
    log_level: str = "INFO"
    slot_granularity_minutes: int = 15  # A-05
    min_lead_time_minutes: int = 60  # A-06
    booking_horizon_days: int = 90  # A-07
    alternatives_count: int = 3  # FR-06
    alternatives_search_days: int = 7  # FR-06

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            service_name=os.getenv("APP_SERVICE_NAME", cls.service_name),
            environment=os.getenv("APP_ENV", cls.environment),
            database_url=os.getenv("APP_DATABASE_URL") or None,
            db_pool_max_size=int(os.getenv("APP_DB_POOL_MAX_SIZE", str(cls.db_pool_max_size))),
            seed_demo_data=_bool("APP_SEED_DEMO_DATA", False),
            log_level=os.getenv("APP_LOG_LEVEL", "INFO").upper(),
            slot_granularity_minutes=int(os.getenv("APP_SLOT_GRANULARITY_MINUTES", "15")),
            min_lead_time_minutes=int(os.getenv("APP_MIN_LEAD_TIME_MINUTES", "60")),
            booking_horizon_days=int(os.getenv("APP_BOOKING_HORIZON_DAYS", "90")),
            alternatives_count=int(os.getenv("APP_ALTERNATIVES_COUNT", "3")),
            alternatives_search_days=int(os.getenv("APP_ALTERNATIVES_SEARCH_DAYS", "7")),
        )
