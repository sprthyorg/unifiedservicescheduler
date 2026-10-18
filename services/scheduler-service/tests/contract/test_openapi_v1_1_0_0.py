"""Contract test: the running app exposes exactly the operations in the baselined OpenAPI document."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

SPEC = Path(__file__).resolve().parents[4] / "04-design/api/scheduler-service/v1/openapi_1.0.0.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}


def _operations(doc: dict[str, Any]) -> set[tuple[str, str]]:
    return {(path, m) for path, item in doc["paths"].items() for m in item if m in METHODS}


def test_spec_and_implementation_expose_the_same_operations(client: TestClient) -> None:
    spec = yaml.safe_load(SPEC.read_text())
    assert spec["info"]["version"] == "1.0.0"
    assert _operations(client.app.openapi()) == _operations(spec)  # type: ignore[attr-defined]


def test_spec_request_schema_matches_pydantic_required_fields(client: TestClient) -> None:
    spec = yaml.safe_load(SPEC.read_text())
    impl = client.app.openapi()["components"]["schemas"]  # type: ignore[attr-defined]
    for name in ("BookAppointmentRequest", "CancelAppointmentRequest"):
        assert set(spec["components"]["schemas"][name]["required"]) == set(impl[name]["required"]), name
