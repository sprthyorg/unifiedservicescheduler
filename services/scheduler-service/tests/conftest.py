from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories.memory import InMemoryDatabase, InMemoryUnitOfWork, seed_demo_data
from app.services.scheduling_service import BookAppointmentCommand, SchedulingService

IST = ZoneInfo("Asia/Kolkata")
DEALER = "DLR-HYD-01"


def ist(day: int, hh: int, mm: int = 0) -> datetime:
    """Wall-clock time in the demo dealership's zone, October 2026 (19th = Monday)."""
    return datetime(2026, 10, day, hh, mm, tzinfo=IST)


class FakeClock:
    def __init__(self) -> None:
        self.now = ist(19, 8, 30)  # Monday 08:30 local

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def db() -> InMemoryDatabase:
    database = InMemoryDatabase()
    seed_demo_data(database)
    return database


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def service(db: InMemoryDatabase, clock: FakeClock) -> SchedulingService:
    return SchedulingService(lambda: InMemoryUnitOfWork(db), clock=clock)


def cmd(
    start: datetime | None = None,
    service_type: str = "SVC-OIL",
    customer: str = "CUS-1001",
    vehicle: str = "VEH-5001",
    dealership: str = DEALER,
) -> BookAppointmentCommand:
    return BookAppointmentCommand(
        customer_id=customer,
        vehicle_id=vehicle,
        dealership_id=dealership,
        service_type_id=service_type,
        desired_start=start or ist(20, 10),
    )


@pytest.fixture
def client(db: InMemoryDatabase, clock: FakeClock) -> Iterator[TestClient]:
    app = create_app(
        Settings(log_level="WARNING"), uow_factory=lambda: InMemoryUnitOfWork(db), database=db, clock=clock
    )
    with TestClient(app) as c:
        yield c


def body(
    start: str = "2026-10-20T10:00:00+05:30",
    service_type: str = "SVC-OIL",
    customer: str = "CUS-1001",
    vehicle: str = "VEH-5001",
) -> dict[str, object]:
    return {
        "customer_id": customer,
        "vehicle_id": vehicle,
        "dealership_id": DEALER,
        "service_type_id": service_type,
        "desired_start_time": start,
    }
