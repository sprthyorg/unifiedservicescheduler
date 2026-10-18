"""Contract test: outbox events match the published JSON schemas (04-design/events/, FR-10)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from app.repositories.memory import InMemoryDatabase
from app.services.scheduling_service import SchedulingService
from tests.conftest import cmd, ist

EVENTS = Path(__file__).resolve().parents[4] / "04-design/events"


def _validate(event_type: str, envelope: dict[str, object]) -> None:
    schema = json.loads((EVENTS / event_type / "v1.schema.json").read_text())
    jsonschema.validate(envelope, schema, format_checker=jsonschema.FormatChecker())


def test_fr_10_events_match_published_schemas(service: SchedulingService, db: InMemoryDatabase) -> None:
    a = service.book_appointment(cmd(ist(20, 10)), "key-ev-01").appointment
    service.cancel_appointment(a.id, customer_id="CUS-1001", reason="test")
    assert [e.type for e in db.outbox] == ["appointment.confirmed", "appointment.cancelled"]
    for e in db.outbox:
        envelope = {
            "id": str(e.id),
            "type": e.type,
            "schema_version": e.schema_version,
            "occurred_at": e.occurred_at.isoformat(),
            "aggregate_id": str(e.aggregate_id),
            "payload": e.payload,
        }
        _validate(e.type, envelope)
