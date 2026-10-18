"""Storage wiring (composition root helper)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from app.config import Settings
from app.domain.ports import UnitOfWork
from app.repositories.memory import InMemoryDatabase, InMemoryUnitOfWork, seed_demo_data


class Pingable(Protocol):
    def ping(self) -> bool: ...


def build_storage(settings: Settings) -> tuple[Pingable, Callable[[], UnitOfWork]]:
    if settings.database_url:
        from app.repositories.postgres import PostgresDatabase, PostgresUnitOfWork

        pg = PostgresDatabase(settings.database_url, max_size=settings.db_pool_max_size)
        return pg, lambda: PostgresUnitOfWork(pg)
    mem = InMemoryDatabase()
    if settings.seed_demo_data:
        seed_demo_data(mem)
    return mem, lambda: InMemoryUnitOfWork(mem)
