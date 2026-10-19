"""Submission validation and persistence for every supported state producer."""

import gzip
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import STATE_TYPES, state_payload


@pytest.mark.parametrize("state_type", STATE_TYPES)
@pytest.mark.parametrize("compressed", [False, True])
def test_submit_persists_supported_payload(
    client: TestClient, store: Any, state_type: str, compressed: bool
) -> None:
    """Plain and gzip JSON persist and enrich all four supported state types."""
    payload = state_payload(state_type)
    raw = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if compressed:
        raw = gzip.compress(raw)
        headers["Content-Encoding"] = "GZIP"
    response = client.post("/api/submit", content=raw, headers=headers)
    assert response.status_code == 200
    saved = store.get_by_device_name("Test Device")
    assert saved["StateFileType"] == state_type
    assert saved["StateURLName"] == "TestDevice"
    assert (
        json.loads((store.state_data_dir / "Test Device.json").read_text()) == payload
    )


@pytest.mark.parametrize("state_type", STATE_TYPES)
def test_submit_missing_and_mistyped_fields(
    client: TestClient, store: Any, state_type: str
) -> None:
    """Every required field is rejected when missing or of the wrong JSON type."""
    payload = state_payload(state_type)
    required = {
        "PowerController": [
            "SaveTime",
            "SchemaVersion",
            "DeviceName",
            "Output",
            "Scheduler",
        ],
        "LightingControl": [
            "LastStateSaveTime",
            "SchemaVersion",
            "DeviceName",
            "RandomOffsets",
            "SwitchStates",
        ],
        "TempProbes": ["SaveTime", "SchemaVersion", "DeviceName", "TempProbeLogging"],
        "OutputMetering": [
            "SaveTime",
            "SchemaVersion",
            "DeviceName",
            "Summary",
            "Meters",
        ],
    }
    for field in required[state_type]:
        missing = dict(payload)
        del missing[field]
        response = client.post("/api/submit", json=missing)
        assert response.status_code == 400
        assert response.json()["error"] == f"Missing required key: {field}"
        response = client.post("/api/submit", json=dict(payload, **{field: None}))
        assert response.status_code == 400
        assert response.json()["error"].startswith(f"Key '{field}' must be ")
    assert store.count() == 0
    assert list(store.state_data_dir.iterdir()) == []


@pytest.mark.parametrize(
    ("body", "headers", "error"),
    [
        (b"{}", {"Content-Type": "text/plain"}, "Expected application/json"),
        (b"broken", {"Content-Type": "application/json"}, "Invalid JSON"),
        (b"[]", {"Content-Type": "application/json"}, "Expected a JSON object"),
        (b"null", {"Content-Type": "application/json"}, "Expected a JSON object"),
        (
            b"bad gzip",
            {"Content-Type": "application/json", "Content-Encoding": "gzip"},
            "Failed to decompress payload",
        ),
        (
            gzip.compress(b"not JSON"),
            {"Content-Type": "application/json", "Content-Encoding": "gzip"},
            "Failed to decompress payload",
        ),
        (
            b'{"StateFileType": "Other"}',
            {"Content-Type": "application/json"},
            "Unknown StateFileType: Other",
        ),
    ],
)
def test_submit_rejects_invalid_body(
    client: TestClient, store: Any, body: bytes, headers: dict[str, str], error: str
) -> None:
    """Malformed submissions return a useful error without persisting anything."""
    response = client.post("/api/submit", content=body, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"error": error}
    assert store.count() == 0


def test_legacy_submission_defaults_to_power(client: TestClient, store: Any) -> None:
    """Older producers can omit StateFileType and still submit power state."""
    payload = state_payload()
    del payload["StateFileType"]
    assert client.post("/api/submit", json=payload).status_code == 200
    assert (
        store.get_by_device_name("Test Device")["DeviceDescription"]
        == "Power Controller"
    )


def test_submit_replaces_existing_device(client: TestClient, store: Any) -> None:
    """A new save for the same device replaces rather than duplicates its state."""
    payload = state_payload()
    client.post("/api/submit", json=payload)
    payload["Output"]["IsOn"] = False
    assert client.post("/api/submit", json=payload).status_code == 200
    assert store.count() == 1
    assert store.get_by_device_name("Test Device")["Output"]["IsOn"] is False
